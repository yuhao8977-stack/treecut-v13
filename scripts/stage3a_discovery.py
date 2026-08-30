# -*- coding: utf-8 -*-
"""Stage 3A — B003 数据现实汇总：已发现的数据源 + 各源结构摘要。

诚实输出：B003 无数据；B008/坤宝研究设计院为候选替代源（需用户确认身份映射）。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DESK = r"C:\Users\admin\Desktop"
OUT = os.path.join(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1",
                   "B003_DATA_SOURCE_DISCOVERY.json")


def main():
    found = {
        "manifest": "B003_DATA_SOURCE_DISCOVERY",
        "generated_at": "2026-08-30",
        "conclusion": "B003 账号数据不存在；发现 2 个候选 Published Content 源（无 B003 代号映射）",
        "b003_target": {
            "found": False,
            "note": "当前环境（DB/DATA_ROOT/repo/Desktop/Downloads/E盘TreeCut）无任何含 B003 代号的"
                    "发布内容/表现/映射数据；账号清单.docx 仅列 5 个坤宝系账号名，无 B003 代号",
        },
        "discovered_sources": [
            {
                "source_id": "SRC-B008-VIRAL",
                "file": os.path.join(DESK, "【B008】【KUBON坤宝岛台工厂】【0000.00.00起】爆款内容记录表.xlsx"),
                "data_type": "published_content + dmp_performance",
                "account_id": "B008",
                "account_name": "KUBON坤宝岛台工厂",
                "rows_total": 1027,
                "rows_with_note_link": 143,
                "fields_available": ["note_id/链接", "标题", "类型", "点赞/收藏/评论", "互动率",
                                     "视频互动/私信开口", "DMP行为（关键词/笔记行为/行业兴趣/对标账号）",
                                     "直播推广", "商品推广（互动）"],
                "note": "表结构复杂（多级表头+合并单元格+DISPIMG图片），需清洗；"
                        "有投流/DMP 行为列（PAID 信号）",
                "reliability": "MEDIUM（人工维护，字段完整但格式混杂）",
            },
            {
                "source_id": "SRC-KBYSJY-ACCOUNT",
                "file": os.path.join(DESK, "坤宝研究设计院账号内容.xlsx"),
                "data_type": "published_content（图文笔记）",
                "account_id": "UNKNOWN（文件名='坤宝研究设计院'，无 B003 代号映射）",
                "rows_total": 29,
                "rows_with_note": 29,
                "fields_available": ["note_id（如 682c43c4…）", "标题", "类型（科普+避坑/产品/入户产品）",
                                     "封面点击率", "点赞/收藏/评论", "互动率"],
                "note": "29 条真实小红书笔记，note_id 完整；无投流/私信/加微信数据",
                "reliability": "MEDIUM（人工维护）",
            },
            {
                "source_id": "SRC-XHS-REGISTER",
                "file": os.path.join(DESK, "小红书运营登记表【图文-核心数据】.xlsx"),
                "data_type": "account-level daily register（账号级，非 note 级）",
                "account_id": "UNKNOWN",
                "rows_total": 53,
                "rows_with_data": 1,
                "fields_available": ["日期", "消耗", "线索数量", "后台/前台私信", "留微信数量",
                                     "加微数量/成本", "转化单数", "观看", "互动数", "新增粉丝"],
                "note": "账号级汇总（非 note 级）；仅 1 行有效数据；含 added-WeChat 归集字段"
                        "（集中归集不可反推单视频）",
                "reliability": "LOW（仅 1 行有效）",
            },
            {
                "source_id": "SRC-GROUP-RECONCILIATION",
                "file": os.path.join(DESK, "【G组】坤宝岛台对账表2025.6.1更新.xlsx"),
                "data_type": "销售订单/对账（非内容表现）",
                "account_id": "G组",
                "rows_total": 24,
                "note": "订单/客户/分成数据，与内容链路无 note 级关联；不可用于 Content DNA",
                "reliability": "N/A（非内容数据）",
            },
        ],
        "needed_for_b003_pilot": [
            "B003 账号的 note 发布清单（note_id/title/publish_time）",
            "B003 的 note 级表现快照（views/likes/favorites/comments/私信/线索）",
            "B003 的 note→asset 映射（或至少视频文件可匹配）",
            "B003 的投流记录（spend/paid_impressions/paid_leads，如存在）",
            "added-WeChat 可归因性确认（集中归集则标 UNATTRIBUTABLE）",
        ],
        "recommendation": "需用户确认：1) B003 对应哪个账号名（账号清单 5 个候选）；"
                          "2) 是否允许以 B008 或坤宝研究设计院作为 Pilot 替代（数据更完整）；"
                          "3) B003 数据是否需要另行导出导入。",
        "guard": "不得虚构 B003 数据；账号身份未确认前禁止 Content DNA",
    }
    json.dump(found, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
