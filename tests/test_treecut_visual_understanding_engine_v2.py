import unittest

from treecut.services.visual_understanding_v2 import (
    Action, TemporalDecision, ShotCandidate, IslandClaimLibrary,
    DomainVisualCritic, Support, Verdict, DuplicateCritic, DuplicateEvidence,
    VisualBeatGrouper, NoCandidateResolver
)

class TestTreeCutVisualUnderstandingV2(unittest.TestCase):
    def setUp(self):
        self.lib = IslandClaimLibrary()
        self.critic = DomainVisualCritic()

    def shot(self, action, objects=None, completeness="COMPLETE"):
        return ShotCandidate(
            segment_id="x", asset_id="a", start_s=0, end_s=2.5,
            production_eligible=True, contamination_free=True,
            objects=objects or [],
            temporal=TemporalDecision(
                action=action, completeness=completeness,
                direction_supported=action not in (Action.STATIC, Action.UNKNOWN),
                object_supported=True,
                reason_codes=[], support=Support.SUPPORTED
            )
        )

    def test_socket_closeup_not_extend(self):
        req = self.lib.requirement("c", "b", "来客时一拉就变宽")
        s = self.shot(Action.SOCKET_ADJUST, ["TRACK_SOCKET", "SOCKET_MODULE"])
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)
        self.assertIn("DOMINANT_VISUAL_MISMATCH", d.reason_codes)

    def test_retract_not_extend(self):
        req = self.lib.requirement("c", "b", "来客时一拉就变宽")
        s = self.shot(Action.RETRACT, ["TABLETOP"])
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)
        self.assertIn("OPPOSITE_ACTION", d.reason_codes)

    def test_extend_not_retract(self):
        req = self.lib.requirement("c", "b", "平时收起来不占位")
        s = self.shot(Action.EXTEND, ["TABLETOP"])
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)
        self.assertIn("OPPOSITE_ACTION", d.reason_codes)

    def test_static_extended_table_not_extend_action(self):
        req = self.lib.requirement("c", "b", "来客时一拉就变宽")
        s = self.shot(Action.STATIC, ["TABLETOP"])
        s.states = ["TABLETOP_EXTENDED_STATE"]
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)

    def test_static_table_can_support_function_claim(self):
        req = self.lib.requirement("c", "b", "伸缩桌面")
        s = self.shot(Action.STATIC, ["TABLETOP"])
        d = self.critic.review(req, s)
        self.assertNotEqual(d.verdict, Verdict.FAIL)

    def test_drawer_close_not_open(self):
        req = self.lib.requirement("c", "b", "打开就能拿到")
        s = self.shot(Action.DRAWER_CLOSE, ["DRAWER"])
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)

    def test_generic_drawer_not_upper_thin_drawer(self):
        req = self.lib.requirement("c", "b", "上层薄抽")
        s = self.shot(Action.STATIC, ["DRAWER"])
        d = self.critic.review(req, s)
        self.assertEqual(d.verdict, Verdict.FAIL)
        self.assertIn("UPPER_THIN_DRAWER_UNVERIFIED", d.reason_codes)

    def test_no_candidate_core_claim_rewrite(self):
        req = self.lib.requirement("c", "b", "插拔也顺手")
        r = NoCandidateResolver().decide(req, 0)
        self.assertEqual(r["decision"], "REWRITE_DROP_OR_BLOCK")

    def test_visual_beat_not_one_shot_per_ordinal(self):
        phrases = [
            "岛台想好用", "这三个细节最值得看",
            "第一", "上层薄抽", "收纳小物不弯腰", "打开就能拿到",
            "第二", "轨道插座", "吃火锅煮茶都方便", "插拔也顺手",
            "第三", "伸缩桌面", "来客时一拉就变宽", "平时收起来不占位",
            "厨房好不好用", "全在这些小细节里",
        ]
        groups = VisualBeatGrouper().group(phrases)
        self.assertLessEqual(len(groups), 6)
        self.assertGreaterEqual(len(groups), 4)
        self.assertTrue(any("第一" in "".join(g) and "上层薄抽" in "".join(g) for g in groups))

    def test_narrative_duplicate_requires_multiple_signals(self):
        d = DuplicateCritic().review(DuplicateEvidence(
            same_person=True, same_product=True, same_composition=False, same_shot_role=False
        ))
        self.assertEqual(d["verdict"], "NOT_DUPLICATE")

        d2 = DuplicateCritic().review(DuplicateEvidence(
            same_person=True, same_product=True, same_composition=True, same_shot_role=True
        ))
        self.assertEqual(d2["verdict"], "NARRATIVE_NEAR_DUPLICATE")

if __name__ == "__main__":
    unittest.main()

