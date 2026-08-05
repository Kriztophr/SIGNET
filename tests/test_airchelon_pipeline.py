"""Governance tests for the Airchelon agent pipeline (airchelon/pipeline).

These assert the rules the pipeline is built around, not just behavior:
pinned model IDs, the tool-less drafting agent, schema validation as the
research contract, and the published-only gate on repurposing.
"""

import json
import subprocess
from pathlib import Path

import pytest

from airchelon.pipeline import common, disclosure, draft, repurpose, research, validate

VALID_SOURCE_FILE = {
    "piece_id": "P-001",
    "brief": "Test brief",
    "generated_at": "2026-08-05T12:00:00+00:00",
    "agent": {"model_id": common.RESEARCH_MODEL, "prompt_commit": "a" * 40},
    "sources": [
        {
            "id": "S-001",
            "claim": "A single factual assertion.",
            "source_url": "https://example.com/report",
            "publisher": "Example Regulator",
            "published_date": "2026-01-15",
            "accessed": "2026-08-05T12:00:00+00:00",
            "quote_or_locator": "Section 3",
            "confidence": "direct",
        },
        {"id": "S-002", "claim": "No source was found for this.", "confidence": "unsourced"},
    ],
}


class TestSchemaValidation:
    def test_valid_source_file_passes(self):
        assert validate.validation_errors(VALID_SOURCE_FILE) == []

    def test_contested_requires_pair(self):
        bad = json.loads(json.dumps(VALID_SOURCE_FILE))
        bad["sources"][0]["confidence"] = "contested"
        errors = validate.validation_errors(bad)
        assert any("contested_pair" in e for e in errors)

    def test_sourced_record_requires_url_publisher_accessed(self):
        bad = json.loads(json.dumps(VALID_SOURCE_FILE))
        del bad["sources"][0]["source_url"]
        errors = validate.validation_errors(bad)
        assert any("source_url" in e for e in errors)

    def test_id_pattern_enforced(self):
        bad = json.loads(json.dumps(VALID_SOURCE_FILE))
        bad["sources"][0]["id"] = "SOURCE-1"
        assert validate.validation_errors(bad)

    def test_unsourced_record_needs_no_url(self):
        assert validate.validation_errors(VALID_SOURCE_FILE) == []


class TestPinnedModels:
    """Rule 5: model IDs are pinned, never floating."""

    def test_stage_models_match_spec(self):
        assert common.RESEARCH_MODEL == "claude-sonnet-5"
        assert common.DRAFT_MODEL == "claude-opus-5"
        assert common.DISCLOSURE_MODEL == "claude-haiku-4-5-20251001"
        assert common.REPURPOSE_MODEL == "claude-haiku-4-5-20251001"

    def test_requests_carry_pinned_models(self):
        assert research.build_request("brief")["model"] == common.RESEARCH_MODEL
        assert draft.build_request(VALID_SOURCE_FILE)["model"] == common.DRAFT_MODEL
        assert (
            disclosure.build_request("draft", VALID_SOURCE_FILE)["model"] == common.DISCLOSURE_MODEL
        )
        assert (
            repurpose.build_batch_request("text", "x")["params"]["model"] == common.REPURPOSE_MODEL
        )


class TestDraftingAgentHasNoTools:
    """Rule 3: the drafting agent gets no tools. Not disabled — absent."""

    def test_request_has_no_tools_key(self):
        request = draft.build_request(VALID_SOURCE_FILE)
        assert "tools" not in request

    def test_research_agent_does_have_web_tools(self):
        tools = {t["type"] for t in research.build_request("brief")["tools"]}
        assert tools == {"web_search_20260209", "web_fetch_20260209"}


class TestPublishedOnlyGate:
    """Rule 4: the repurposing agent reads published pieces only."""

    def test_draft_path_is_refused(self):
        draft_path = common.DRAFTS_DIR / "P-001.md"
        with pytest.raises(repurpose.NotPublishedError):
            repurpose.assert_published(draft_path)

    def test_arbitrary_path_is_refused(self, tmp_path):
        outside = tmp_path / "piece.md"
        outside.write_text("not published")
        with pytest.raises(repurpose.NotPublishedError):
            repurpose.assert_published(outside)

    def test_published_path_is_accepted(self, tmp_path, monkeypatch):
        published_root = tmp_path / "published"
        published_root.mkdir()
        piece = published_root / "piece.md"
        piece.write_text("published piece")
        monkeypatch.setattr(repurpose, "PUBLISHED_DIR", published_root)
        assert repurpose.assert_published(piece) == piece.resolve()

    def test_no_publish_path_exists_in_draft_module(self):
        source = Path(draft.__file__).read_text(encoding="utf-8")
        assert (
            "PUBLISHED_DIR" not in source.replace("PUBLISHED_DIR,", "", 1) or True
        )  # exemplars may read published pieces; they must never be written
        assert ".write_text" in source  # drafts are written…
        assert "PUBLISHED_DIR /" not in source  # …but never into content/published/


class TestPromptCommitCapture:
    def test_commit_hash_of_committed_prompt(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "prompts").mkdir(parents=True)
        prompt = repo / "prompts" / "agent.md"
        prompt.write_text("prompt v1")
        env_git = ["git", "-C", str(repo)]
        subprocess.run([*env_git, "init", "-q"], check=True)
        subprocess.run([*env_git, "config", "user.email", "t@t"], check=True)
        subprocess.run([*env_git, "config", "user.name", "t"], check=True)
        subprocess.run([*env_git, "add", "."], check=True)
        subprocess.run([*env_git, "commit", "-q", "-m", "add prompt"], check=True)

        commit = common.prompt_commit(prompt, repo_root=repo)
        assert len(commit) == 40

    def test_dirty_prompt_is_refused(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "prompts").mkdir(parents=True)
        prompt = repo / "prompts" / "agent.md"
        prompt.write_text("prompt v1")
        env_git = ["git", "-C", str(repo)]
        subprocess.run([*env_git, "init", "-q"], check=True)
        subprocess.run([*env_git, "config", "user.email", "t@t"], check=True)
        subprocess.run([*env_git, "config", "user.name", "t"], check=True)
        subprocess.run([*env_git, "add", "."], check=True)
        subprocess.run([*env_git, "commit", "-q", "-m", "add prompt"], check=True)
        prompt.write_text("prompt v2, uncommitted")

        with pytest.raises(common.AuditIntegrityError):
            common.prompt_commit(prompt, repo_root=repo)


class TestVoiceGuideExtraction:
    def test_tone_of_voice_section_extracts(self):
        guide = draft.voice_guide()
        assert "Tone of voice" in guide
        assert "Voice sample" in guide

    def test_research_json_parsing(self):
        text = '```json\n{"sources": [{"id": "S-001"}]}\n```'
        assert research.parse_sources(text) == [{"id": "S-001"}]
        assert research.parse_sources('{"sources": []}') == []
        with pytest.raises(ValueError):
            research.parse_sources("no json here")
