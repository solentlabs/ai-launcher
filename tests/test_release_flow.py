"""Tests for the release script's CI-waiting and tag-resume logic.

scripts/release.py had no test coverage at all, which is how three bugs reached
a live release. Each scenario that actually failed on v0.4.2 has a named
regression test here.

Author: Solent Labs™
Created: 2026-08-06
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

_spec = importlib.util.spec_from_file_location("release_mod", SCRIPTS / "release.py")
release_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_mod)


# The two commits from the v0.4.2 release these regressions are drawn from:
# 615ae4c is the release merge that should have been waited on, 2b19fe9 the
# earlier commit whose stale green run was read instead. Padded rather than
# written out in full so the entropy scanner does not read a git hash as a
# credential; only their distinctness matters to the tests.
MERGE_SHA = "615ae4c" + "0" * 33
STALE_SHA = "2b19fe9" + "0" * 33


def _gh_result(payload):
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


class TestPollMainCi:
    """Waiting for CI on the commit that will actually be tagged."""

    def test_ignores_stale_run_from_an_earlier_commit(self):
        """Regression: this is why v0.4.2 tagged into a running CI.

        Right after the squash-merge the new run has not registered, so the run
        list contains only the *previous* commit's run -- already green. Matching
        on recency instead of SHA returned success immediately and phase 8 pushed
        the tag while CI on the real commit had not started.
        """
        calls = []

        def fake_run_gh(args, check=False):
            calls.append(args)
            if len(calls) == 1:
                # Only the previous commit's completed, successful run exists.
                return _gh_result(
                    [
                        {
                            "status": "completed",
                            "conclusion": "success",
                            "databaseId": 31101948417,
                            "headSha": STALE_SHA,
                        }
                    ]
                )
            return _gh_result(
                [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 31105439770,
                        "headSha": MERGE_SHA,
                    },
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 31101948417,
                        "headSha": STALE_SHA,
                    },
                ]
            )

        with patch.object(release_mod, "run_gh", side_effect=fake_run_gh):
            with patch.object(release_mod.time, "sleep"):
                assert release_mod.poll_main_ci(MERGE_SHA) is True

        # It must not have accepted the first (stale) response.
        assert len(calls) >= 2, "returned before the real run appeared"

    def test_waits_while_the_matching_run_is_in_progress(self):
        responses = [
            _gh_result(
                [
                    {
                        "status": "in_progress",
                        "conclusion": None,
                        "databaseId": 1,
                        "headSha": MERGE_SHA,
                    }
                ]
            ),
            _gh_result(
                [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 1,
                        "headSha": MERGE_SHA,
                    }
                ]
            ),
        ]

        with patch.object(release_mod, "run_gh", side_effect=responses):
            with patch.object(release_mod.time, "sleep"):
                assert release_mod.poll_main_ci(MERGE_SHA) is True

    def test_failure_on_the_matching_run_is_fatal(self):
        response = _gh_result(
            [
                {
                    "status": "completed",
                    "conclusion": "failure",
                    "databaseId": 9,
                    "headSha": MERGE_SHA,
                }
            ]
        )
        with patch.object(release_mod, "run_gh", return_value=response):
            with patch.object(release_mod.time, "sleep"):
                with pytest.raises(SystemExit):
                    release_mod.poll_main_ci(MERGE_SHA)

    def test_failure_on_a_different_commit_is_ignored(self):
        """A red run on an unrelated commit must not fail this release."""
        responses = [
            _gh_result(
                [
                    {
                        "status": "completed",
                        "conclusion": "failure",
                        "databaseId": 7,
                        "headSha": STALE_SHA,
                    }
                ]
            ),
            _gh_result(
                [
                    {
                        "status": "completed",
                        "conclusion": "success",
                        "databaseId": 8,
                        "headSha": MERGE_SHA,
                    },
                    {
                        "status": "completed",
                        "conclusion": "failure",
                        "databaseId": 7,
                        "headSha": STALE_SHA,
                    },
                ]
            ),
        ]
        with patch.object(release_mod, "run_gh", side_effect=responses):
            with patch.object(release_mod.time, "sleep"):
                assert release_mod.poll_main_ci(MERGE_SHA) is True


class TestCheckTagNotExists:
    """Phase 1 must permit resuming the release it already started."""

    def _fake_run(self, tag_listing, tagged_sha, head_sha):
        def _run(cmd, capture=False, check=True):
            if cmd[:3] == ["git", "tag", "-l"]:
                return SimpleNamespace(stdout=tag_listing, returncode=0, stderr="")
            if cmd[:2] == ["git", "rev-list"]:
                return SimpleNamespace(stdout=tagged_sha, returncode=0, stderr="")
            if cmd[:2] == ["git", "rev-parse"]:
                return SimpleNamespace(stdout=head_sha, returncode=0, stderr="")
            return SimpleNamespace(stdout="", returncode=0, stderr="")

        return _run

    def test_absent_tag_is_available(self):
        with patch.object(
            release_mod, "run", side_effect=self._fake_run("", "", MERGE_SHA)
        ):
            release_mod.check_tag_not_exists("0.4.3")  # must not raise

    def test_tag_at_head_allows_resume(self):
        """Regression: v0.4.2's GitHub release had to be created by hand.

        Phase 8 stopped on a tag-protection failure with the tag already pushed,
        and re-running fatally exited in phase 1 rather than finishing the job.
        """
        run = self._fake_run("v0.4.2\n", MERGE_SHA, MERGE_SHA)
        with patch.object(release_mod, "run", side_effect=run):
            release_mod.check_tag_not_exists("0.4.2")  # must not raise

    def test_tag_on_a_different_commit_is_still_fatal(self):
        """The safety property survives: a tag pointing elsewhere is a conflict."""
        run = self._fake_run("v0.4.2\n", STALE_SHA, MERGE_SHA)
        with patch.object(release_mod, "run", side_effect=run):
            with pytest.raises(SystemExit):
                release_mod.check_tag_not_exists("0.4.2")
