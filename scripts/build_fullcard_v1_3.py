#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a script-free Zenless Zone Zero CCV3 from frozen source files."""
import json
import hashlib
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"assembly"
BOOK=OUT/"worldbook"/"dist"
CARD=OUT/"card"/"dist"
QA=OUT/"qa"
rows=[]
used=set()
fingerprints={}
counts=Counter()
checks=[]
forbidden=("getvar(","<%","StatusPlaceHolderImpl","[mvu_update]","NSFW Helper","NSFW Char Stage","<script","javascript:","mvu_zod.js","MagVarUpdate/artifact")
allowed=("worldbook/blue/BLUE-","worldbook/green/blue","worldbook/green/core/GREEN-","worldbook/characters/major/CHAR-","worldbook/characters/bangboo/official/BOO-","worldbook/characters/bangboo/original/BOO-","worldbook/abilities/ABILITY-","worldbook/abilities/states/STATE-","worldbook/timeline/TIMELINE-","worldbook/locations/blue/LOCATION-BLUE-","worldbook/locations/green/")
def need(label,ok,detail=""):
    checks.append([label,bool(ok),detail])
    if not ok: raise AssertionError(label+": "+str(detail))
def read(src,front=None,back=None):
    need("source prefix "+src,src.startswith(allowed))
    p=(ROOT/src).resolve()
    need("valid path "+src,p.is_relative_to(ROOT) and p.is_file())
    need("no duplicate file "+src,src not in used)
    used.add(src)
    s=p.read_text(encoding="utf-8").strip()
    fingerprints[src]=hashlib.sha256(p.read_bytes()).hexdigest()
    need("content exists "+src,len(s)>0)
    if front: need("opening tag "+src,s.startswith(front+"\n"),repr(s[:65]))
    if back: need("closing tag "+src,s.endswith(back),repr(s[-65:]))
    need("no old runtime "+src,not any(z in s for z in forbidden))
    return s
def meta(path): return json.loads((ROOT/path).read_text(encoding="utf-8"))
def add(title,text,order,category,keys=None,active=True,constant=False,regex=False,pos="after_char",guard=True,source=None):
    keys=list(keys or [])
    need("content "+title,bool(text) or not active or category=="section_marker")
    need("order type "+title,type(order) is int)
    need("valid position "+title,pos in ("before_char","after_char","at_depth"))
    need("runtime removed "+title,not any(z in text for z in forbidden))
    row={"id":0,"keys":keys,"secondary_keys":[],"comment":title,"content":text,
         "constant":constant,"selective":bool(keys) and not constant,
         "insertion_order":order,"enabled":active,"position":pos,"use_regex":regex,
         "extensions":{"position":4 if pos=="at_depth" else (0 if pos=="before_char" else 1),
          "exclude_recursion":guard,"prevent_recursion":guard,
          "display_index":0,"probability":100,"useProbability":True,"depth":0 if pos=="at_depth" else (0 if constant else 4),
          "selectiveLogic":0,"scan_depth":None,"match_whole_words":False,
          "case_sensitive":False,"role":0}}
    rows.append(row);counts[category]+=1
SECTION_NAMES={"Locations":"地点","NPC_Characters":"其他角色","Main_Characters":"主要角色","Core_Settings":"核心设定","Core_Rules":"核心规则","Output_Rules":"输出规则","Memory_Context":"记忆相关"}
SECTION_ORDERS={"Locations":(99,1),"NPC_Characters":(199,100),"Main_Characters":(299,200),"Core_Settings":(441,300),"Core_Rules":(459,442),"Output_Rules":(549,460),"Memory_Context":(555,551)}
def marker(tag,open_tag,order,pos):
    # Fullstack mother template: empty section markers, in descending order.
    label=SECTION_NAMES[tag]
    idx=0 if open_tag else 1
    add("【"+label+((":起始】" if open_tag else ":结尾】") if tag=="Memory_Context" else ("：起始】" if open_tag else "：结尾】")),"",SECTION_ORDERS[tag][idx],
        "section_marker",constant=True,pos="after_char",guard=False)
def status_regex(aliases):
    token="|".join(re.escape(a) for a in dict.fromkeys(aliases) if a)
    need("location regex has aliases",bool(token))
    return "/<status>(?:(?!<\\/status>)[\\s\\S])*?当前位置\\s*[:：][^\\n<]*?(?:"+token+")[^\\n<]*(?:(?!<\\/status>)[\\s\\S])*?<\\/status>/"

def scene_regex(aliases):
    pattern="|".join(re.escape(a) for a in dict.fromkeys(aliases) if a)
    return "/<story_scene>(?:(?!<\\/story_scene>)[\\s\\S])*?(?:"+pattern+")(?:(?!<\\/story_scene>)[\\s\\S])*?<\\/story_scene>/"

# A: exact fullstack locations, 71 unique places.
marker("Locations",True,1,"after_char")
locations=meta("worldbook/locations/000_地点绿灯正式装配元数据_v1.1.json")["entries"]
need("71 locations",len(locations)==71,str(len(locations)))
for i,x in enumerate(locations):
    cfg=x["build"]
    need("location green double recursion "+x["id"],cfg["extensions"]["exclude_recursion"] and cfg["extensions"]["prevent_recursion"])
    need("location activation "+x["id"],cfg["enabled"] and not cfg["constant"])
    add("地点:"+x["title"],read(x["body_file"],"<地点:"+x["title"]+">","</地点:"+x["title"]+">"),
        2+i,"location_green",keys=[status_regex(cfg["keys"])],regex=True,source=x["body_file"])
marker("Locations",False,99,"after_char")

# B: independent Bangboo, no individual ability entries.
marker("NPC_Characters",True,100,"after_char")
bmeta=meta("worldbook/characters/bangboo/000_邦布角色装配元数据_v1.2.json")
bangboo=[x for x in bmeta["entries"] if x.get("enabled",bmeta["defaults"]["enabled"])]
need("59 enabled bangboos",len(bangboo)==59)
need("three unverified omitted",len(bmeta["entries"])==62 and len(bangboo)==59)
for i,x in enumerate(bangboo):
    name=x["name"]
    need("bangboo keys scoped "+name,all("<story_scene>" in k for k in x["keys"]))
    add("角色:"+name,read(x["path"],"<"+name+"character>","</"+name+"character>"),
        101+i,"bangboo_character",keys=x["keys"],regex=True,source=x["path"])
marker("NPC_Characters",False,199,"after_char")

# C: 82 distinct named characters, including the Bangboo Jian Shu.
marker("Main_Characters",True,200,"after_char")
cs=sorted((ROOT/"worldbook/characters/major").glob("CHAR-[0-9][0-9][0-9]_*.md"))
need("82 source characters",len(cs)==82)
names={};triggers={}
for i,p in enumerate(cs):
    n=int(p.stem.split("_",1)[0].split("-")[1]);name=p.stem.split("_",1)[1]
    need("sequential character ID",n==i+1,str(n))
    names[n]=name
    al=[name]
    if "·" in name and len(name.split("·",1)[0])>=2:al.append(name.split("·",1)[0])
    if n==1:al.append("Belle")
    if n==2:al.append("Wise")
    if n==50:al+=["奥菲丝","鬼火"]
    if n==73:al.append("瑟汐")
    triggers[n]=[scene_regex(al)]
    src=p.relative_to(ROOT).as_posix()
    add("角色:"+name,read(src,"<"+name+"character>","</"+name+"character>"),
        201+i,"main_character",keys=triggers[n],regex=True,source=src)
marker("Main_Characters",False,299,"after_char")

# D: 54 regular GREEN, 81 character abilities, 5 special states.
marker("Core_Settings",True,300,"after_char")
gm=meta("worldbook/green/000_核心绿灯静态触发方案_v2.6.json")
gs=[x for x in gm["entries"] if x.get("build")]
need("54 core greens",len(gs)==54)
for i,x in enumerate(gs):
    cfg=x["build"]
    need("core GREEN double recursion "+x["id"],cfg["extensions"]["exclude_recursion"] and cfg["extensions"]["prevent_recursion"])
    add("核心设定:"+x["title"],read(x["body_file"],"<"+x["content_tag"]+">","</"+x["content_tag"]+">"),
        301+i,"regular_green",keys=[scene_regex(cfg["keys"])],regex=True,source=x["body_file"])
all_abilities=sorted((ROOT/"worldbook/abilities").glob("ABILITY-[0-9][0-9][0-9]_*.md"))
need("82 ability sources",len(all_abilities)==82)
abilities=[x for x in all_abilities if not x.name.startswith("ABILITY-064_")]
need("exclude former Jian Shu ability",len(abilities)==81)
for i,p in enumerate(abilities):
    n=int(p.stem.split("_",1)[0].split("-")[1]);name=names[n];src=p.relative_to(ROOT).as_posix()
    add("核心设定:"+name+"·能力",read(src,"<核心设定:"+name+"·能力>","</核心设定:"+name+"·能力>"),
        355+i,"character_ability",keys=triggers[n],regex=True,source=src)
states=meta("worldbook/abilities/states/000_特殊状态装配元数据_v1.4.json")["states"]
need("five state entries",len(states)==5)
for i,x in enumerate(states):
    add(x["comment"],read(x["body_file"],"<"+x["comment"]+">","</"+x["comment"]+">"),
        436+i,"special_state",keys=x["keys"],regex=True,source=x["body_file"])
marker("Core_Settings",False,441,"after_char")

# E: 9 immutable world BLUE + 5 distinct always-on regional BLUE.
marker("Core_Rules",True,442,"before_char")
blues=sorted((ROOT/"worldbook/blue").glob("BLUE-[0-9][0-9]_*.md"))
need("nine world blues",len(blues)==9)
for i,p in enumerate(blues):
    src=p.relative_to(ROOT).as_posix()
    add("世界蓝灯:"+p.stem.split("_",1)[1],read(src),443+i,"world_blue",constant=True,
        pos="before_char",guard=False,source=src)
lbs=meta("worldbook/locations/000_常驻地点蓝灯装配元数据_v1.0.json")["entries"]
need("five location blues",len(lbs)==5)
for i,x in enumerate(lbs):
    src=x["path"];title=x["title"]
    add("地点蓝灯:"+title,read(src,"<地域总览:"+title+">","</地域总览:"+title+">"),
        452+i,"location_blue",constant=True,pos="before_char",guard=False,source=src)
battle=("<战斗推演原则>\n交战从地形、距离、装备、对手行动和人物已知能力展开。"
        "攻防需要时机、体能与协同；强敌可以迫使撤退，空洞侵蚀、伤势与物资消耗具有真实后果。"
        "胜负由实际过程形成，不靠凭空开挂、无视限制或重复无限连招。\n</战斗推演原则>")
add("战斗思维链",battle,490,"battle_reasoning",constant=True,pos="at_depth",guard=False)
marker("Core_Rules",False,459,"before_char")

# F: 29 standalone volumes, ONLY first part initially on.
marker("Output_Rules",True,460,"before_char")
tfiles=sorted((ROOT/"worldbook/timeline").glob("000_*_装配元数据_v1.0.json"))
need("29 timeline part metadata",len(tfiles)==29)
timelines=sorted([json.loads(p.read_text(encoding="utf-8")) for p in tfiles],key=lambda x:x["insertion_order"])
need("timeline source orders unique",len(set(x["insertion_order"] for x in timelines))==29)
activated=[]
for i,x in enumerate(timelines):
    src=x["body_file"]
    text=read(src,"<world_timeline>","</world_timeline>")
    need("one timeline per entry "+src,text.count("<world_timeline>")==1 and text.count("</world_timeline>")==1)
    need("timeline begins event A "+src,re.search(r"^-事件A(?:\s|:|1:)",text,re.M)!=None)
    need("timeline contains sandbox "+src,"沙盒模式" in text)
    if x["enabled"]:activated.append(src)
    add(x["comment"],text,489-i,"timeline",active=bool(x["enabled"]),constant=True,
        pos="at_depth",guard=False,source=src)
need("only first upper volume enabled",activated==["worldbook/timeline/TIMELINE-001-上_法厄同启程.md"],repr(activated))
out=("<叙事输出约定>\n新艾利都的场景与人物随对话连续发展。角色只知道当前已发生、"
     "自己能掌握的事实；时间线分册由用户手动选择，不自动进入后续分册。"
     "铃是佩洛伊斯唯一寄宿者，哲是她的非寄宿绳匠搭档。日常可自然展开，"
     "不强迫剧情跳转、提前剧透、凭空授予装备或抹除既有伤势。\n</叙事输出约定>")
add("输出规则:开放沙盒叙事",out,491,"narrative_output",constant=True,pos="at_depth",guard=False)
topics=("<新艾利都日常话题>\n六分街可以聊录像、街机、拉面与邦布改装；外环有车队、补给和矿区，"
        "卫非地有茶楼、山路和辉瓷市集，罗斯凯利法有学校、岛屿、企业与研究设施。"
        "日常、人际往来和小型委托都应符合当前所在场所与既有时间线。\n</新艾利都日常话题>")
add("核心规则:城市日常话题",topics,458,"open_topic_pool",
    keys=[scene_regex(["自由探索","闲聊","日常委托","沙盒模式"])],regex=True,pos="after_char")
marker("Output_Rules",False,549,"before_char")

# G: Fullstack v1.0.0 original memory slots, OFF unless manually enabled.
marker("Memory_Context",True,555,"after_char")
memory=("<叙事连续记忆>\n角色的既有行动、物品、关系和已知秘密以真实对话及当前启用分册为准。"
        "未启用的将来剧情不能被默认视作已发生；不依赖变量脚本保存或强制清空故事。\n</叙事连续记忆>")
add("核心规则:叙事连续性",memory,457,"memory_continuity",constant=True,pos="after_char",guard=False)
clearvars="{{setvar::combat_driver::}}\n{{setvar::status_format::}}\n{{setvar::世界书重大记忆存储::}}\n{{setvar::世界书日常记忆存储::}}\n{{setvar::世界书玩家身世背景::}}"
add("🗑️清空局部变量(别关)",clearvars,560,"disabled_infrastructure",constant=True,pos="before_char",guard=False)
memory_storage=[
    ("日常记忆存储", "{{setvar::世界书日常记忆存储::\n【xx年x月x日至xx年x月x日】:xxxx (例子，自行替换)\n}}", 554),
    ("重大记忆存储", "{{setvar::世界书重大记忆存储::\n核心设定：\n(记录改变故事的大事件)\n}}", 553),
    ("玩家身世背景", "{{setvar::世界书玩家身世背景::\n<user>身世背景:\n}}", 552),
]
for title,body,order in memory_storage:
    add(title,body,order,"disabled_infrastructure",active=False,constant=True,pos="after_char",guard=False)
marker("Memory_Context",False,551,"after_char")

expected={"world_blue":9,"location_blue":5,"regular_green":54,"main_character":82,
          "character_ability":81,"special_state":5,"bangboo_character":59,
          "location_green":71,"timeline":29,"section_marker":14,"narrative_output":1,
          "battle_reasoning":1,"open_topic_pool":1,"memory_continuity":1,
          "disabled_infrastructure":4}
need("all group counts",all(counts[k]==v for k,v in expected.items()),dict(counts))
need("all unique insertion orders",len(set(x["insertion_order"] for x in rows))==len(rows))
need("exactly 14 marker rows",sum(x["comment"].startswith("【") and (":起始" in x["comment"] or "：起始" in x["comment"] or "：结尾" in x["comment"]) for x in rows)==14)
for tag in ["Locations","NPC_Characters","Main_Characters","Core_Settings","Core_Rules","Output_Rules","Memory_Context"]:
    st=next(x for x in rows if x["comment"]=="【"+SECTION_NAMES[tag]+(":起始】" if tag=="Memory_Context" else "：起始】"))
    end=next(x for x in rows if x["comment"]=="【"+SECTION_NAMES[tag]+(":结尾】" if tag=="Memory_Context" else "：结尾】"))
    need("marker order "+tag,st["insertion_order"]>end["insertion_order"])
    need("marker same position "+tag,st["position"]==end["position"])
    need("marker guard off "+tag,not st["extensions"]["exclude_recursion"] and not end["extensions"]["prevent_recursion"])
for x in rows:
    if not x["constant"] and x["enabled"]:
        need("trigger double guard "+x["comment"],x["extensions"]["exclude_recursion"] and x["extensions"]["prevent_recursion"])
    need("no instructions in entry "+x["comment"],not any(z in x["content"] for z in
        ("docs/001_","qa/068_","施工单","GitHub HEAD:","源码路径:","STATUSPLACEHOLDER","<StatusPlaceHolder")))
rows.sort(key=lambda x:x["insertion_order"],reverse=True)
for i,x in enumerate(rows):
    x["id"]=i+1;x["extensions"]["display_index"]=i

greeting="""<opening>
（说明:正常开场-随机设定）
（时间:以已启用的【时间线】条目为锚点；未启用时由当前故事合理确定）

输入[随机开始]开始故事。

<!--
[Location Pool]（按概率选其一，不能预先当作剧情已发生）：
1. 六分街 30%：磨旧的石板路、拉面香气、旧霓虹招牌。难度⭐
2. 光映广场 25%：高楼广告屏、拥挤地铁口和电影灯箱。难度⭐
3. Random Play附近 20%：旧影像海报、录像店木门与晚风。难度⭐
4. 芭莱大厦前 10%：古典立面、喷泉水声、通勤人群。难度⭐⭐
5. 外环野火镇 10%：加油站、车轮扬尘、远处荒原。难度⭐⭐⭐
6. 斯科特前哨外围 5%：监测设备、警戒灯与守卫。难度⭐⭐⭐⭐
[Identity Pool]：
1. 普通市民或旅行者 35%
2. 店铺帮工或影像收藏者 25%
3. 调查员学徒 20%
4. 外环补给商 15%
5. 临时委托协助者 5%
[以太适性 Pool]：
1. 普通耐受 80%
2. 受过防护训练 17%
3. 较高适性 3%
[Spawn Roulette]：
1. 按各池概率独立决定玩家初始处境，再呈现可供玩家回应的第一幕；例：在六分街作为影像收藏者看见旧海报，或在外环以补给商身份遇见返程车队。
2. 场景保留该地区的气味、光照与声音；依当前已启用分册的年月日与已发生事件判断角色认知。
3. 现代城市有邦布、地铁、空洞防护与以太能源；不能将空洞当成地下普通洞穴。
4. 不强制结识主角，不提前给予佩洛伊斯寄宿能力、虚狩头衔、装备与终局情报；铃仍为唯一寄宿者，哲是其非寄宿搭档。
5. 等待玩家输入，不替玩家选择行动或推进未触发的卷。
-->
</opening>"""
alternate_greetings=[
"""<opening>
（说明:备选开场-六分街日常）
（时间:以已启用的【时间线】条目为锚点）
输入[随机开始]开始故事。
<!-- 地点在六分街与Random Play周边二选一，各50%。身份在熟客40%、新邻居35%、临时帮工25%之间抽取。以咖啡香、旧海报与店家人声展开第一幕；只描写公开营业情况，法厄同身份不能当街公开，铃的寄宿秘密不得提前揭示；不要替玩家作答。 -->
</opening>""",
"""<opening>
（说明:备选开场-外环旅程）
（时间:以已启用的【时间线】条目为锚点）
输入[随机开始]开始故事。
<!-- 野火镇60%、外环公路30%、老油田安全外围10%。身份在车队随行人45%、补给商35%、旅行者20%之间抽取；以油料气味、荒野公路与机修声作为感官基础。除非当前时间线确实发生，不得预设玩家认识卡吕冬之子、胜任空洞作战或继承组织称号；不要替玩家作答。 -->
</opening>"""
]
name="绝区零｜新艾利都·咩咩全栈完整沙盒"
description=("《绝区零》新艾利都原著开放世界角色卡。九条世界蓝灯、五条地点常驻骨架，"
             "配合人物、组织、邦布、能力、地点与14卷29篇独立时间线。"
             "唯一佩洛伊斯寄宿者为铃，哲仍作为法厄同搭档共同参与。")
scenario=("从六分街、外环、卫非地或罗斯凯利法自由进入开放世界，"
          "自定义玩家身份；默认仅第一卷（上）时间线启用，其余分册需手动切换。"
          "不使用MVU、状态栏、酒馆助手脚本或旧变量引擎。")
book={"name":"绝区零｜咩咩全栈·完整世界书","entries":rows,"extensions":{},"recursive_scanning":False}
data={"name":name,"description":description,
      "personality":"新艾利都多人物群像沙盒，以世界内各人物自有性格行动。",
      "scenario":scenario,"first_mes":greeting,"mes_example":"",
      "creator_notes":"非官方《绝区零》同人世界书与角色卡；以用户原卡结构与公开游戏资料重新精修。游戏权利归原权利人；原卡作者署名及授权以原资料为准。",
      "system_prompt":"","post_history_instructions":"",
      "tags":["绝区零","Zenless Zone Zero","咩咩全栈","新艾利都","SillyTavern"],
      "creator":"3086013261qq-hue","character_version":"v1.3.0",
      "alternate_greetings":alternate_greetings,"extensions":{"talkativeness":0.5,"fav":False,"world":book["name"]},
      "character_book":book}
card={"spec":"chara_card_v3","spec_version":"3.0","data":data,
      "name":name,"description":description,"personality":data["personality"],
      "scenario":scenario,"first_mes":greeting,"mes_example":"",
      "creatorcomment":data["creator_notes"],"avatar":"none",
      "talkativeness":0.5,"fav":False,"tags":data["tags"]}
need("primary world binding",data["extensions"]["world"]==book["name"] and len(book["entries"])==418)
need("no runtime extensions",not any(k in data["extensions"] for k in ("tavern_helper","regex_scripts","mvu")))
need("one timeline enabled",sum(x["enabled"] for x in rows if x["comment"].startswith("时间线:"))==1)
ordered_tl=[x["comment"] for x in rows if x["comment"].startswith("时间线:")]
need("timeline chronological listing",len(ordered_tl)==29 and ordered_tl[0].startswith("时间线:第一卷（上）") and ordered_tl[-1].startswith("时间线:第十四卷（下）"))
need("mother memory slots",[(x["comment"],x["insertion_order"],x["enabled"]) for x in rows if x["comment"] in ("日常记忆存储","重大记忆存储","玩家身世背景")]==[("日常记忆存储",554,False),("重大记忆存储",553,False),("玩家身世背景",552,False)])
need("expected exact worldbook entries",len(rows)==sum(expected.values()),str(len(rows)))
for path in [BOOK,CARD,QA]:path.mkdir(parents=True,exist_ok=True)
book_path=BOOK/"绝区零_咩咩全栈_完整世界书_v1.3.0.json"
card_path=CARD/"绝区零_咩咩全栈_完整角色卡_v1.3.0.json"
compact=lambda obj: json.dumps(obj,ensure_ascii=False,separators=(",",":"))
book_path.write_text(compact(book),encoding="utf-8")
card_path.write_text(compact(card),encoding="utf-8")
need("book roundtrip",len(json.loads(book_path.read_text(encoding="utf-8"))["entries"])==len(rows))
need("ccv3 embedded book roundtrip",
     json.loads(card_path.read_text(encoding="utf-8"))["data"]["character_book"]["entries"]==
     json.loads(book_path.read_text(encoding="utf-8"))["entries"])
try: head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
except Exception: head="UNKNOWN"
summary={"status":"STATIC_CCV3_QA_PASS_ANDROID_NOT_TESTED","primary_lorebook_ref":book["name"],"embedded_worldbook_install_required":True,"head":head,
         "entries":len(rows),"category_counts":dict(counts),"expected":expected,
         "source_files":len(used),"checks_run":len(checks),"checks_failed":0,
         "only_enabled_timeline":activated,"all_14_markers":True,
         "source_sha256":fingerprints,"scripts_included":False,
         "qa_generated_at":datetime.now(timezone.utc).isoformat(),
         "ccv3_sha256":hashlib.sha256(card_path.read_bytes()).hexdigest(),
         "card_bytes":card_path.stat().st_size,"worldbook_bytes":book_path.stat().st_size,
         "android_sillytavern":"NOT_RUN","png_embed":"LOCAL_COVER_PENDING"}
(QA/"QA-078_装卡检查_v1.3.0.json").write_text(
    json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
(QA/"QA-078_装卡检查_v1.3.0.md").write_text(
    "# 《绝区零》正式CCV3装配QA-078\n\n"+
    "状态：SOURCE STATIC QA PASS；ANDROID NOT TESTED。\n\n"+
    "仓库HEAD: "+head+"\n\n"+
    "世界书条目： "+str(len(rows))+"；完整分类："+str(dict(counts))+"\n\n"+
    "主要世界书绑定字段与内嵌世界书名称一致；14个分区标记全在；54普通绿灯与全部触发型双重防递归；首卷上单独开启；"+
    "29时间线独立；缄枢不添加ABILITY-064；3来源待核邦布不装卡；"+
    "无旧状态脚本/NSFW开关/getvar/EJS；读取正式源稿未带入docs/QA。\n",
    encoding="utf-8")
print(json.dumps({"status":"PASS","head":head,"total":len(rows),"counts":dict(counts),
                  "checks":len(checks),"card_bytes":card_path.stat().st_size,
                  "book_bytes":book_path.stat().st_size},ensure_ascii=False))
