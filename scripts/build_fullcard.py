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
    need("content "+title,bool(text) or not active)
    need("order type "+title,type(order) is int)
    need("valid position "+title,pos in ("before_char","after_char"))
    need("runtime removed "+title,not any(z in text for z in forbidden))
    row={"id":0,"keys":keys,"secondary_keys":[],"comment":title,"content":text,
         "constant":constant,"selective":bool(keys) and not constant,
         "insertion_order":order,"enabled":active,"position":pos,"use_regex":regex,
         "extensions":{"position":0 if pos=="before_char" else 1,
          "exclude_recursion":guard,"prevent_recursion":guard,
          "display_index":0,"probability":100,"useProbability":True,"depth":0 if constant else 4,
          "selectiveLogic":0,"scan_depth":None,"match_whole_words":False,
          "case_sensitive":False,"role":0}}
    rows.append(row);counts[category]+=1
def marker(tag,open_tag,order,pos):
    content=("<"+tag+">") if open_tag else ("</"+tag+">")
    add(("分区起始:" if open_tag else "分区结束:")+tag,content,order,
        "section_marker",constant=True,pos=pos,guard=False)
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
    need("location activation "+x["id"],cfg["enabled"] and not cfg["constant"] and not cfg["use_regex"])
    add("地点:"+x["title"],read(x["body_file"],"<地点:"+x["title"]+">","</地点:"+x["title"]+">"),
        2+i,"location_green",keys=cfg["keys"],source=x["body_file"])
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
    add("邦布角色:"+name,read(x["path"],"<"+name+"character>","</"+name+"character>"),
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
    add(x["id"]+" "+x["title"],read(x["body_file"],"<"+x["content_tag"]+">","</"+x["content_tag"]+">"),
        301+i,"regular_green",keys=cfg["keys"],regex=cfg["use_regex"],source=x["body_file"])
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
add("咩咩全栈·战斗思维链（静态）",battle,457,"battle_reasoning",constant=True,pos="before_char")
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
    add(x["comment"],text,461+i,"timeline",active=bool(x["enabled"]),constant=True,
        pos="before_char",source=src)
need("only first upper volume enabled",activated==["worldbook/timeline/TIMELINE-001-上_法厄同启程.md"],repr(activated))
out=("<叙事输出约定>\n新艾利都的场景与人物随对话连续发展。角色只知道当前已发生、"
     "自己能掌握的事实；时间线分册由用户手动选择，不自动进入后续分册。"
     "铃是佩洛伊斯唯一寄宿者，哲是她的非寄宿绳匠搭档。日常可自然展开，"
     "不强迫剧情跳转、提前剧透、凭空授予装备或抹除既有伤势。\n</叙事输出约定>")
add("输出规则:开放沙盒叙事",out,491,"narrative_output",constant=True,pos="before_char")
topics=("<新艾利都日常话题>\n六分街可以聊录像、街机、拉面与邦布改装；外环有车队、补给和矿区，"
        "卫非地有茶楼、山路和辉瓷市集，罗斯凯利法有学校、岛屿、企业与研究设施。"
        "日常、人际往来和小型委托都应符合当前所在场所与既有时间线。\n</新艾利都日常话题>")
add("开放话题池:城市日常",topics,492,"open_topic_pool",
    keys=["自由探索","闲聊","日常委托","沙盒模式"],pos="before_char")
marker("Output_Rules",False,549,"before_char")

# G: static memory continuity + no-script placeholders, default OFF.
marker("Memory_Context",True,550,"before_char")
memory=("<叙事连续记忆>\n角色的既有行动、物品、关系和已知秘密以真实对话及当前启用分册为准。"
        "未启用的将来剧情不能被默认视作已发生；不依赖变量脚本保存或强制清空故事。\n</叙事连续记忆>")
add("记忆:叙事连续性",memory,551,"memory_continuity",constant=True,pos="before_char")
for i,title in enumerate(["清空局部变量（无脚本预留）","记忆槽:长期概要（预留）",
                          "记忆槽:当前情境（预留）","记忆槽:人物关系（预留）",
                          "状态栏:默认（禁用占位）"]):
    add(title,"",552+i,"disabled_infrastructure",active=False,pos="before_char")
marker("Memory_Context",False,559,"before_char")

expected={"world_blue":9,"location_blue":5,"regular_green":54,"main_character":82,
          "character_ability":81,"special_state":5,"bangboo_character":59,
          "location_green":71,"timeline":29,"section_marker":14,"narrative_output":1,
          "battle_reasoning":1,"open_topic_pool":1,"memory_continuity":1,
          "disabled_infrastructure":5}
need("all group counts",all(counts[k]==v for k,v in expected.items()),dict(counts))
need("all unique insertion orders",len(set(x["insertion_order"] for x in rows))==len(rows))
need("exactly 14 marker rows",sum(x["comment"].startswith("分区") for x in rows)==14)
for tag in ["Locations","NPC_Characters","Main_Characters","Core_Settings","Core_Rules","Output_Rules","Memory_Context"]:
    st=next(x for x in rows if x["comment"]=="分区起始:"+tag)
    end=next(x for x in rows if x["comment"]=="分区结束:"+tag)
    need("marker order "+tag,st["insertion_order"]<end["insertion_order"])
    need("marker same position "+tag,st["position"]==end["position"])
    need("marker guard off "+tag,not st["extensions"]["exclude_recursion"] and not end["extensions"]["prevent_recursion"])
for x in rows:
    if not x["constant"] and x["enabled"]:
        need("trigger double guard "+x["comment"],x["extensions"]["exclude_recursion"] and x["extensions"]["prevent_recursion"])
    need("no instructions in entry "+x["comment"],not any(z in x["content"] for z in
        ("docs/001_","qa/068_","施工单","GitHub HEAD:","源码路径:","STATUSPLACEHOLDER","<StatusPlaceHolder")))
rows.sort(key=lambda x:x["insertion_order"])
for i,x in enumerate(rows):
    x["id"]=i+1;x["extensions"]["display_index"]=i

greeting=("<story_scene>\n2077年04月15日，新艾利都·六分街，傍晚。\n\n"
          "霓虹灯沿着街头一盏盏亮起，拉面馆的汤锅冒着热气，街机厅传来断续的电子乐。"
          "几只圆乎乎的邦布迈着小短腿穿过路人，面屏上闪着好奇的表情。\n\n"
          "Random Play录像店的门半开着，铃正在整理影碟，哲则在柜台后翻阅委托记录。"
          "城外空洞的异常光晕映在远处的建筑上，城市里寻常而热闹的一天仍在继续。\n\n"
          "故事可以从街头相遇开始，也可以从另一处街区的生活、旅行或委托切入。"
          "你打算如何走进新艾利都？\n</story_scene>")
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
      "creator":"3086013261qq-hue","character_version":"v1.0.0",
      "alternate_greetings":[],"extensions":{"talkativeness":0.5,"fav":False},
      "character_book":book}
card={"spec":"chara_card_v3","spec_version":"3.0","data":data,
      "name":name,"description":description,"personality":data["personality"],
      "scenario":scenario,"first_mes":greeting,"mes_example":"",
      "creatorcomment":data["creator_notes"],"avatar":"none",
      "talkativeness":0.5,"fav":False,"tags":data["tags"]}
need("no runtime extensions",not any(k in data["extensions"] for k in ("tavern_helper","regex_scripts","mvu")))
need("one timeline enabled",sum(x["enabled"] for x in rows if x["comment"].startswith("时间线:"))==1)
need("expected exact worldbook entries",len(rows)==sum(expected.values()),str(len(rows)))
for path in [BOOK,CARD,QA]:path.mkdir(parents=True,exist_ok=True)
book_path=BOOK/"绝区零_咩咩全栈_完整世界书_v1.0.0.json"
card_path=CARD/"绝区零_咩咩全栈_完整角色卡_v1.0.0.json"
compact=lambda obj: json.dumps(obj,ensure_ascii=False,separators=(",",":"))
book_path.write_text(compact(book),encoding="utf-8")
card_path.write_text(compact(card),encoding="utf-8")
need("book roundtrip",len(json.loads(book_path.read_text(encoding="utf-8"))["entries"])==len(rows))
need("ccv3 embedded book roundtrip",
     json.loads(card_path.read_text(encoding="utf-8"))["data"]["character_book"]["entries"]==
     json.loads(book_path.read_text(encoding="utf-8"))["entries"])
try: head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
except Exception: head="UNKNOWN"
summary={"status":"STATIC_CCV3_QA_PASS_ANDROID_NOT_TESTED","head":head,
         "entries":len(rows),"category_counts":dict(counts),"expected":expected,
         "source_files":len(used),"checks_run":len(checks),"checks_failed":0,
         "only_enabled_timeline":activated,"all_14_markers":True,
         "source_sha256":fingerprints,"scripts_included":False,
         "qa_generated_at":datetime.now(timezone.utc).isoformat(),
         "ccv3_sha256":hashlib.sha256(card_path.read_bytes()).hexdigest(),
         "card_bytes":card_path.stat().st_size,"worldbook_bytes":book_path.stat().st_size,
         "android_sillytavern":"NOT_RUN","png_embed":"LOCAL_COVER_PENDING"}
(QA/"QA-069_装卡检查_v1.0.0.json").write_text(
    json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
(QA/"QA-069_装卡检查_v1.0.0.md").write_text(
    "# 《绝区零》正式CCV3装配QA-069\n\n"+
    "状态：SOURCE STATIC QA PASS；ANDROID NOT TESTED。\n\n"+
    "仓库HEAD: "+head+"\n\n"+
    "世界书条目： "+str(len(rows))+"；完整分类："+str(dict(counts))+"\n\n"+
    "14个分区标记全在；54普通绿灯与全部触发型双重防递归；首卷上单独开启；"+
    "29时间线独立；缄枢不添加ABILITY-064；3来源待核邦布不装卡；"+
    "无旧状态脚本/NSFW开关/getvar/EJS；读取正式源稿未带入docs/QA。\n",
    encoding="utf-8")
print(json.dumps({"status":"PASS","head":head,"total":len(rows),"counts":dict(counts),
                  "checks":len(checks),"card_bytes":card_path.stat().st_size,
                  "book_bytes":book_path.stat().st_size},ensure_ascii=False))
