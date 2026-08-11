"""事件引擎 — 包装 event_calendar，统一品种筛选、到期校验、事件定价判断"""

import os
import sys
from typing import List, Optional, Dict

_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from event_calendar import get_upcoming_events
from .config import VARIETIES


class EventEngine:
    """事件引擎：包装 event_calendar.get_upcoming_events()

    提供品种筛选、到期校验、事件定价 shortcut（IV>70%分位+事件≤5d→买方降级）。
    """

    def __init__(self, days: int = 14, varieties: List[str] = None):
        self.events = get_upcoming_events(days=days, varieties=varieties)

    def for_variety(self, vcode: str, variety_name: str) -> List[dict]:
        """筛选与指定品种相关的事件"""
        relevant = []
        for e in self.events:
            ev_vcodes = e.get("varieties", [])
            ev_names = e.get("variety_names", [])
            if vcode in ev_vcodes or variety_name in ev_names:
                relevant.append(e)
        return relevant

    def has_tier1(self, vcode: str, variety_name: str) -> bool:
        """是否有 Tier1 事件（非例行+高冲击+0-7天）→ 买方第一关"""
        for e in self.for_variety(vcode, variety_name):
            if (not e.get("routine", True)
                    and e.get("impact", "low") == "high"
                    and 0 <= e.get("days_until", 0) <= 7):
                return True
        return False

    def has_d1_high(self, vcode: str, variety_name: str) -> bool:
        """是否有 D-0/D-1 高影响事件 → 卖方避让"""
        for e in self.for_variety(vcode, variety_name):
            if (e.get("impact") == "high"
                    and 0 <= e.get("days_until", 0) <= 1):
                return True
        return False

    def nearest_event_days(self, vcode: str, variety_name: str) -> Optional[int]:
        """最近事件天数（排除持续事件 days_until=-1）"""
        dated = [e for e in self.for_variety(vcode, variety_name)
                 if e.get("days_until", 0) >= 0]
        if not dated:
            return None
        return min(e["days_until"] for e in dated)

    def event_too_late(self, vcode: str, variety_name: str, dte: int) -> bool:
        """事件是否在到期后才发生"""
        nearest = self.nearest_event_days(vcode, variety_name)
        if nearest is None:
            return False
        return nearest > dte - 1

    @staticmethod
    def is_all_tier3(events: List[dict]) -> bool:
        """是否仅有例行低冲击事件 → 不产生买方方向信号"""
        if not events:
            return True
        has_meaningful = any(
            not e.get("routine", True) or e.get("impact", "low") != "low"
            for e in events
        )
        return not has_meaningful

    @staticmethod
    def is_event_priced(iv_percentile: Optional[float],
                        events: List[dict],
                        threshold_pct: int = 70,
                        within_days: int = 5) -> bool:
        """事件定价 shortcut：IV 已膨胀 + 事件临近 → 买方不应进场。

        IV 分位 >70% 说明市场已对风险定价，此时买期权 = 为膨胀 IV 付费。
        """
        if iv_percentile is None or iv_percentile < threshold_pct:
            return False

        dated = [e for e in events if e.get("days_until", 0) >= 0]
        if not dated:
            return False

        nearest = min(e["days_until"] for e in dated)
        return nearest <= within_days

    def get_ongoing_events(self) -> List[dict]:
        """持续性地缘事件（days_until=-1）"""
        return [e for e in self.events if e.get("days_until") == -1]

    def get_high_events(self, max_days: int = 14) -> List[dict]:
        """高影响固定日期事件，按天数排序"""
        high = [e for e in self.events
                if e["impact"] == "high" and e.get("days_until", -1) >= 0]
        high.sort(key=lambda e: e["days_until"])
        return high[:max_days]

    def get_medium_events(self, max_days: int = 5) -> List[dict]:
        """中影响事件（窗口内）"""
        return [e for e in self.events
                if e["impact"] == "medium" and 0 <= e.get("days_until", -1) <= max_days]

    def get_event_vcodes(self, max_days: int = 7) -> set:
        """获取近期有高影响事件的品种码集合"""
        vcodes = set()
        for e in self.events:
            if e["impact"] == "high" and e.get("days_until", -1) <= max_days:
                for vn in e.get("variety_names", []):
                    # 品种名→码映射
                    for vc, vi in VARIETIES.items():
                        if vi["name"] == vn:
                            vcodes.add(vc)
        return vcodes
