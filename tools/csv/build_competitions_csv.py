#!/usr/bin/env python3
"""从「大学竞赛.xlsx」生成 competitions.csv。"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XLSX = Path(r"e:\中石大竞赛排行\大学竞赛.xlsx")
DEFAULT_OUT = ROOT / "datasets" / "master" / "competitions.csv"

CATEGORY_TO_TYPE: dict[str, str] = {
    "综合类": "创新创业",
    "计算机类": "程序设计",
    "理学类": "学科竞赛",
    "电子信息类": "学科竞赛",
    "医学类": "学科竞赛",
    "其他工学类": "学科竞赛",
    "语言类": "学科竞赛",
    "艺术类": "学科竞赛",
    "职业技能类": "职业技能",
    "机器人类": "学科竞赛",
    "农学类": "学科竞赛",
    "经管类": "学科竞赛",
}

CATEGORY_TO_CAP: dict[str, str] = {
    "综合类": "cap_req_innovation|cap_req_teamwork|cap_req_social|cap_req_growth",
    "计算机类": "cap_req_theory|cap_req_practice|cap_req_digital|cap_req_growth",
    "理学类": "cap_req_theory|cap_req_cross|cap_req_practice|cap_req_innovation",
    "电子信息类": "cap_req_theory|cap_req_practice|cap_req_digital|cap_req_innovation",
    "医学类": "cap_req_theory|cap_req_practice|cap_req_teamwork|cap_req_social",
    "其他工学类": "cap_req_practice|cap_req_theory|cap_req_innovation|cap_req_teamwork",
    "语言类": "cap_req_social|cap_req_cross|cap_req_growth|cap_req_teamwork",
    "艺术类": "cap_req_innovation|cap_req_practice|cap_req_cross|cap_req_growth",
    "职业技能类": "cap_req_practice|cap_req_digital|cap_req_growth|cap_req_teamwork",
    "机器人类": "cap_req_practice|cap_req_digital|cap_req_innovation|cap_req_teamwork",
    "农学类": "cap_req_practice|cap_req_cross|cap_req_innovation|cap_req_teamwork",
    "经管类": "cap_req_social|cap_req_theory|cap_req_teamwork|cap_req_innovation",
}

CATEGORY_TO_JOBS: dict[str, str] = {
    "综合类": "项目经理/主管|产品专员/助理|管培生/储备干部",
    "计算机类": "Java|C/C++|前端开发|测试工程师|软件测试",
    "理学类": "科研人员|统计员|Java|C/C++",
    "电子信息类": "C/C++|硬件测试|科研人员|Java",
    "医学类": "科研人员",
    "其他工学类": "C/C++|硬件测试|风电工程师|科研人员",
    "语言类": "英语翻译|日语翻译|内容审核",
    "艺术类": "内容审核|产品专员/助理",
    "职业技能类": "Java|C/C++|测试工程师|实施工程师|技术支持工程师",
    "机器人类": "C/C++|科研人员|Java",
    "农学类": "科研人员",
    "经管类": "BD经理|商务专员|销售工程师|咨询顾问|项目专员/助理",
}

CATEGORY_TO_DIFFICULTY: dict[str, str] = {
    "综合类": "高阶",
    "计算机类": "进阶",
    "理学类": "进阶",
    "电子信息类": "进阶",
    "医学类": "进阶",
    "其他工学类": "进阶",
    "语言类": "入门",
    "艺术类": "入门",
    "职业技能类": "入门",
    "机器人类": "高阶",
    "农学类": "进阶",
    "经管类": "进阶",
}

# 2024 全国普通高校学科竞赛排行榜（84 项）官方网址，按 Excel 序号维护
# 参考：上海理工大学创新创业学院《教育部认可的大学生学科竞赛网站链接》及各赛事官网
URL_BY_RANK: dict[int, str] = {
    1: "https://cy.ncss.cn/",
    2: "http://www.tiaozhanbei.net/",
    3: "http://www.tiaozhanbei.net/",
    4: "https://icpc.global/",
    5: "http://www.mcm.edu.cn/",
    6: "http://www.nuedcchina.com/",
    7: "https://www.cmte.org.cn/",
    8: "http://11umic.hust.edu.cn/",
    9: "http://www.structurecontest.com/",
    10: "http://www.sun-ada.net/",
    11: "http://smartcar.moocollege.com/datacenter",
    12: "http://www.3chuang.net/",
    13: "http://www.gcxl.edu.cn/",
    14: "http://www.clpp.org.cn/",
    15: "http://uchallenge.unipus.cn/",
    16: "http://www.nvsc.com.cn/",
    17: "http://gjcxcy.bjtu.edu.cn/Index.aspx",
    18: "https://www.robomaster.com/zh-CN",
    19: "http://www.robotac.cn/",
    20: "http://www.siemenscup-cimc.org.cn/",
    21: "https://iche.zju.edu.cn/",
    22: "http://www.chengtudasai.com/",
    23: "https://jsjds.blcu.edu.cn/",
    24: "http://www.china-cssc.org/",
    25: "http://www.fwwb.org.cn/",
    26: "http://www.china-cssc.org/list-52-1.html",
    27: "http://www.c4best.cn/",
    28: "https://worldskills.org/",
    29: "http://worldskillschina.mohrss.gov.cn/",
    30: "http://www.cnrobocon.net/",
    31: "http://www.ciscn.cn/",
    32: "http://zpy.cstam.org.cn/index.aspx",
    33: "http://meicc.cmes.org/#blade/competition?id=10",
    34: "https://dasai.lanqiao.cn/",
    35: "http://www.mse-cn.com/",
    36: "http://www.cnsoftbei.com/",
    37: "http://gd.p.moocollege.com/",
    38: "http://www.ncda.org.cn/",
    39: "https://chinaus-maker.cscse.edu.cn/",
    40: "https://yuanxi.cugb.edu.cn/competition/",
    41: "http://www.milan-aap.org.cn/",
    42: "http://univ.ciciec.com/",
    43: "https://www.caairobot.com/",
    44: "http://ssyth.cubec.org.cn/",
    45: "https://www.cdec.org.cn/",
    46: "https://3dds.3ddl.net/",
    47: "http://www.xcbds.com/cyds/index",
    48: "http://dtcup.dtxiaotangren.com/",
    49: "http://wlsycx.moocollege.com/",
    50: "http://gxbsxs.glodonedu.com/",
    51: "https://www.raicom.com.cn/",
    52: "https://www.culsc.cn/",
    53: "https://e.huawei.com/cn/talent/#/ict/contest?compId=&nType=talentAlliance",
    54: "http://www.socchina.net/",
    55: "http://www.robotcontest.cn/",
    56: "https://www.jienengjianpai.org/",
    57: "https://contest.i21st.cn/index.php",
    58: "http://www.g-ican.com/home/index",
    59: "https://www.gonghangbei.com/",
    60: "https://jdsxj.eduyun.cn/",
    61: "https://ict.sflep.com/",
    62: "https://star.baidu.com/#/",
    63: "http://www.cuidc.net/",
    64: "https://sljzw.hhu.edu.cn/fenhui/main.psp",
    65: "http://www.cteic.com/higherEducation-199.html",
    66: "https://cid.nju.edu.cn/",
    67: "https://compiler.educg.net/#/",
    68: "http://www.lalavision.com/fjyl/ch/index.aspx",
    69: "http://iot.sjtu.edu.cn/Default.aspx",
    70: "https://www.isclab.org.cn/",
    71: "http://smt.whu.edu.cn/",
    72: "http://tjjmds.ai-learning.net/",
    73: "http://www.ceeia.cn/",
    74: "http://www.jcyxds.com/",
    75: "http://mit.caai.cn/index.php?m=wap",
    76: "http://ssfkds.moocollege.com/",
    77: "http://www.ibizsim.com.cn/",
    78: "https://www.seentao.com/",
    79: "http://bisai.ccen.com.cn/",
    80: "http://www.digix.org.cn/",
    81: "https://uiaec.ujs.edu.cn/",
    82: "http://match.xmkeyun.com.cn/nc/",
    83: "http://www.brskills.com/",
    84: "https://matiji.net/exam/contest/topic?id=1",
}

ORGANIZER_BY_RANK: dict[int, str] = {
    1: "教育部等部委",
    2: "共青团中央、中国科协、教育部",
    3: "共青团中央、中国科协、教育部",
    4: "ICPC Foundation",
    15: "外语教学与研究出版社",
    16: "教育部",
    20: "西门子（中国）有限公司",
    34: "工业和信息化部人才交流中心",
    53: "华为技术有限公司",
    59: "中国工商银行",
    62: "百度在线网络技术（北京）有限公司",
    77: "中国管理现代化研究会",
    78: "中国商业联合会、新道科技股份有限公司",
}

DESC_BY_RANK: dict[int, str] = {
    1: "互联网+大赛面向大学生创新创业项目，要求提交商业计划并进行路演答辩，综合考察创新意识、商业模式、团队协作与社会价值，是影响力最大的双创赛事之一。",
    4: "ACM-ICPC 是全球最具影响力的大学生程序设计竞赛，限时完成算法题设计与实现，重点考察数据结构、算法、编码与团队协作能力。",
    5: "全国大学生数学建模竞赛要求在有限时间内完成建模、求解与论文撰写，考察数学理论、数据分析、建模思维与团队协作。",
    12: "三创赛聚焦电子商务领域的创新、创意与创业，含常规赛与实战赛，考察商业策划、电商运营与团队协同能力。",
    23: "中国大学生计算机设计大赛涵盖软件应用、物联网、人工智能等类别，强调作品创新性与完整度，适合锻炼计算机综合应用能力。",
    34: "蓝桥杯涵盖 C/C++/Java/Python 等赛道，兼顾算法、工程实践与信息技术应用，是国内参与面最广的编程类竞赛之一。",
    36: "中国软件杯由工信部支持，面向大学生软件设计，强调产教融合与工程化开发能力，适合软件工程相关专业学生。",
    62: "百度之星程序设计大赛是国内历史最久、影响力较大的企业级编程赛事之一，考察算法、编码与问题求解能力。",
    67: "计算机系统能力大赛含 CPU、操作系统、编译、数据库等多个赛道，面向系统级设计与工程实践能力培养。",
}

SKILL_KEYWORDS: list[tuple[str, str]] = [
    ("程序设计", "算法|数据结构|编程"),
    ("ACM", "算法|数据结构|C++|问题求解"),
    ("ICPC", "算法|数据结构|编程"),
    ("数学建模", "数学建模|数据分析|MATLAB"),
    ("电子设计", "嵌入式|电路设计|硬件开发"),
    ("智能汽车", "嵌入式|自动控制|电子"),
    ("机器人", "机器人|嵌入式|自动控制"),
    ("RoboMaster", "机器人|嵌入式|视觉算法"),
    ("RoboTac", "机器人|机械|控制"),
    ("软件", "软件设计|编程|系统开发"),
    ("计算机", "编程|计算机基础|系统设计"),
    ("蓝桥杯", "算法|编程|Java|C++"),
    ("信息安全", "网络安全|渗透测试|密码学"),
    ("集成电路", "芯片设计|Verilog|硬件"),
    ("光电", "光学|电子|物理"),
    ("机械", "机械设计|CAD|创新设计"),
    ("结构", "结构力学|建模|工程设计"),
    ("化工", "化工设计|流程模拟|实验"),
    ("物流", "供应链|物流规划|数据分析"),
    ("电子商务", "电商运营|商业策划|数据分析"),
    ("互联网+", "商业计划|创新思维|团队协作"),
    ("挑战杯", "科研创新|商业计划|团队协作"),
    ("英语", "英语|口语|写作|翻译"),
    ("外研社", "英语|演讲|表达"),
    ("广告", "广告创意|视觉设计|策划"),
    ("BIM", "BIM|建筑信息模型|工程管理"),
    ("财会", "会计|财务|ERP"),
    ("统计", "统计学|数据分析|建模"),
    ("医学", "临床技能|医学理论|实操"),
    ("农业", "农业装备|机械|创新"),
    ("华为ICT", "网络|云计算|ICT"),
    ("人工智能", "机器学习|深度学习|算法"),
    ("嵌入式", "嵌入式|C语言|硬件"),
    ("物理", "物理实验|理论|测量"),
    ("化学", "化学实验|实验设计|安全"),
    ("测绘", "测绘|GIS|遥感"),
    ("水利", "水利工程|设计|创新"),
    ("物联网", "物联网|嵌入式|系统设计"),
    ("西门子", "智能制造|PLC|自动化"),
    ("成图", "CAD|工程制图|三维建模"),
    ("三维数字化", "3D建模|数字化设计|CAD"),
    ("市场调查", "市场调研|数据分析|问卷"),
    ("服务外包", "软件外包|商业|项目管理"),
    ("金融", "金融科技|产品设计|商业分析"),
    ("沙盘", "企业经营|财务决策|模拟"),
    ("税务", "税法|风控|案例分析"),
    ("程序设计大赛", "算法|编程|Java"),
]


def infer_skill_tags(name: str, category: str) -> str:
    tags: list[str] = []
    for kw, tag_str in SKILL_KEYWORDS:
        if kw in name:
            tags.extend(tag_str.split("|"))
    if not tags:
        defaults = {
            "计算机类": ["编程", "算法", "计算机基础"],
            "综合类": ["创新思维", "项目管理", "商业策划"],
            "理学类": ["数学", "建模", "理论分析"],
            "电子信息类": ["电子技术", "嵌入式", "硬件"],
            "经管类": ["商业分析", "市场调研", "财务"],
            "语言类": ["英语", "翻译", "表达"],
            "艺术类": ["设计", "创意", "视觉表达"],
            "职业技能类": ["职业技能", "实操", "工程实践"],
            "机器人类": ["机器人", "控制", "编程"],
            "医学类": ["医学技能", "临床", "实操"],
            "农学类": ["农业", "装备", "创新"],
            "其他工学类": ["工程设计", "创新", "实操"],
        }
        tags.extend(defaults.get(category, ["专业实践", "创新"]))
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return "|".join(ordered[:6])


def infer_desc(rank: int, name: str, category: str, comp_type: str) -> str:
    if rank in DESC_BY_RANK:
        return DESC_BY_RANK[rank]
    cat_cn = {
        "创新创业": "创新创业",
        "程序设计": "程序设计与算法",
        "学科竞赛": "学科专业",
        "职业技能": "职业技能",
    }.get(comp_type, "学科")
    return (
        f"{name}是面向大学生的{cat_cn}竞赛，"
        f"入选2024年全国普通高校学科竞赛排行榜（{category}），"
        f"旨在提升参赛者的专业理论、实践应用与综合创新能力，"
        f"适合相关领域在校生参与以积累竞赛成果与项目经验。"
    )


def infer_organizer(rank: int, name: str, category: str) -> str:
    if rank in ORGANIZER_BY_RANK:
        return ORGANIZER_BY_RANK[rank]
    if "全国" in name or "中国" in name:
        if category == "计算机类":
            return "教育部高等学校计算机类专业教学指导委员会等"
        if category == "综合类":
            return "教育部等部委/团中央"
        return "教育部相关教指委/学会"
    if "国际" in name or "全球" in name:
        return "国际组织/国内学会"
    return "行业学会/高校联盟"


def infer_team_mode(name: str) -> str:
    if any(k in name for k in ["ACM", "ICPC", "数学建模", "机器人", "电子设计", "机械", "结构", "物流", "挑战杯", "互联网+"]):
        return "团队"
    if any(k in name for k in ["英语", "翻译", "辩论", "蓝桥杯", "程序设计", "算法", "演讲"]):
        return "个人或团队"
    return "团队"


def infer_frequency(name: str) -> str:
    if "赛季" in name or "RoboMaster" in name:
        return "赛季制"
    return "每年"


def infer_target_audience(category: str, name: str) -> str:
    if category == "职业技能类" and "职业院校" in name:
        return "高校及职业院校在校生"
    return "本科在校生"


def load_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=1)
    df.columns = ["rank", "name_total", "name_sub", "category"]
    df = df.dropna(subset=["rank"])
    df["rank"] = df["rank"].astype(int)
    df["name"] = df["name_sub"].fillna(df["name_total"]).astype(str).str.strip()
    df["category"] = df["category"].astype(str).str.strip()
    return df


def build_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, r in df.iterrows():
        rank = int(r["rank"])
        name = str(r["name"]).strip()
        category = str(r["category"]).strip()
        comp_type = CATEGORY_TO_TYPE.get(category, "学科竞赛")
        rows.append(
            {
                "competition_id": f"comp_{rank:03d}",
                "job_name": CATEGORY_TO_JOBS.get(category, "科研人员"),
                "competition_name": name,
                "competition_desc": infer_desc(rank, name, category, comp_type),
                "official_url": URL_BY_RANK.get(rank, ""),
                "competition_type": comp_type,
                "organizer": infer_organizer(rank, name, category),
                "target_audience": infer_target_audience(category, name),
                "team_mode": infer_team_mode(name),
                "frequency": infer_frequency(name),
                "difficulty": CATEGORY_TO_DIFFICULTY.get(category, "进阶"),
                "cap_tags": CATEGORY_TO_CAP.get(category, "cap_req_practice|cap_req_growth"),
                "skill_tags": infer_skill_tags(name, category),
                "award_level": "国家级",
            }
        )
    return rows


def main() -> int:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    if not xlsx.is_file():
        print(f"Excel 不存在: {xlsx}", file=sys.stderr)
        return 1

    df = load_excel(xlsx)
    rows = build_rows(df)
    fieldnames = [
        "competition_id",
        "job_name",
        "competition_name",
        "competition_desc",
        "official_url",
        "competition_type",
        "organizer",
        "target_audience",
        "team_mode",
        "frequency",
        "difficulty",
        "cap_tags",
        "skill_tags",
        "award_level",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    missing_url = sum(1 for r in rows if not r["official_url"])
    print(f"写入 {len(rows)} 条 -> {out}")
    print(f"缺少 official_url: {missing_url} 条")
    return 0 if missing_url == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
