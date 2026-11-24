import json
import os
import time
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# 1. 初始化 Gemini 與自動抓取可用模型清單
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@st.cache_data(ttl=3600)
def get_available_models():
    models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            # 篩選支援文字/視覺辨識的 Gemini 模型，排除語音、向量等非對話模型
            if "gemini" in name and not any(k in name for k in ["embedding", "aqa", "tts", "audio", "live", "imagen", "veo"]):
                models.append(name)
    except Exception:
        pass
    # 優先使用 flash 系列，最多輪流嘗試 4 個可用模型
    models.sort(key=lambda x: (0 if "3.8-flash" in x else 1 if "flash" in x else 2))
    return models[:4] if models else ["gemini-3.8-flash"]

MODEL_FALLBACK_LIST = get_available_models()

TARGETS = {
    "弧邊招潮蟹 (Fiddler Crab - 1分)": {
        "points": 1,
        "hint": "雄蟹有一支巨大的橘紅色或橙黃色大螯，背甲深褐色帶網狀花紋。"
    },
    "清白招潮蟹 (Milky Fiddler Crab - 1分)": {
        "points": 1,
        "hint": "體型較小，全身與大螯皆為明顯的乳白色或淡灰色，無強烈黑白反差。"
    },
    "短指和尚蟹 (Soldier Crab - 2分)": {
        "points": 2,
        "hint": "圓球狀藍灰色小螃蟹，常成群結隊在沙泥地上活動。"
    },
    "萬歲大眼蟹 (Sentinel Crab - 2分)": {
        "points": 2,
        "hint": "眼柄非常細長，雙螯細長且常向上舉起。"
    },
    "台灣招潮蟹 (Taiwanese Fiddler Crab - 4分)": {
        "points": 4,
        "hint": "必須同時具備「深黑或深褐色背甲」與「寬扁修長如剪刀狀的白色大螯」（強烈黑白對比）。若全身偏白請判為不符（那是清白招潮蟹）。"
    },
    "彈塗魚 (Mudskipper - 2分)": {
        "points": 2,
        "hint": "兩棲魚類，有突出的雙眼與胸鰭，在泥灘上爬行或跳躍。"
    }
}

TEAMS = ["Team 1", "Team 2", "Team 3", "Team 4", "Team 5"]

# 2. 共用狀態：紀錄各組解鎖進度與過關照片
@st.cache_resource
def get_game_state():
    progress = {team: {sp: False for sp in TARGETS} for team in TEAMS}
    gallery = []
    return {"progress": progress, "gallery": gallery}

state = get_game_state()
progress = state["progress"]
gallery = state["gallery"]

# 3. 頁面標題與即時集點表
st.set_page_config(page_title="Xiangshan Crab Blitz", page_icon="🦀", layout="centered")
st.title("🦀 香山濕地蟹蟹大搜查")
st.caption("Hallo Krabben! Select your team & target species to unlock points.")

st.subheader("🏆 各組解鎖進度與總分 Live Scoreboard")
board_data = []
for t in TEAMS:
    row = {"組別 Team": t}
    total = 0
    for sp, info in TARGETS.items():
        short_name = sp.split(" ")[0]
        if progress[t][sp]:
            row[short_name] = "✅"
            total += info["points"]
        else:
            row[short_name] = "⬜"
    row["總分 Pts"] = total
    board_data.append(row)

st.dataframe(pd.DataFrame(board_data), hide_index=True, use_container_width=True)

st.divider()

# 4. 學生任務上傳區
st.subheader("📸 上傳照片解鎖物種 Upload & Verify")

col1, col2 = st.columns(2)
with col1:
    team = st.selectbox("1️⃣ 選擇組別 Select Team", TEAMS)

with col2:
    species_options = list(TARGETS.keys())
    target_species = st.selectbox(
        "2️⃣ 選擇要解鎖的目標物種 Target Species",
        species_options,
        format_func=lambda x: f"✅ {x} (已解鎖)" if progress[team][x] else f"⬜ {x}"
    )

if progress[team][target_species]:
    st.info(f"👍 {team} 已經解鎖過「{target_species.split(' ')[0]}」囉！請挑戰其他尚未解鎖的物種。")
else:
    uploaded_file = st.file_uploader(
        f"3️⃣ 上傳你找到的【{target_species.split(' ')[0]}】照片",
        type=["jpg", "jpeg", "png"]
    )

    if uploaded_file and st.button("🚀 提交給 AI 裁判驗證 (Verify)", type="primary"):
        img = Image.open(uploaded_file)
        st.image(img, caption=f"{team} 挑戰項目：{target_species}", use_container_width=True)

        # 轉成標準 RGB 並縮小至 1024px，加快海邊上傳速度
        img_for_ai = img.convert("RGB")
        img_for_ai.thumbnail((1024, 1024))

        target_hint = TARGETS[target_species]["hint"]
        prompt = f"""
        你是新竹香山濕地生態競賽的雙語 AI 裁判。
        學生目前聲稱這張照片拍到的是：【{target_species}】。
        該物種的辨識特徵為：{target_hint}

        請檢驗這張照片並以 JSON 格式回傳結果（不要加 markdown 標記）：
        照片中的生物是否真的是【{target_species}】？（考量學生在木棧道遠距離變焦拍攝，畫質可能略微模糊，若特徵相符請從寬認定；但若是明顯不同物種，例如拿清白招潮蟹冒充台灣招潮蟹，請判為 false）。

        回傳格式：
        {{
          "is_match": true 或 false,
          "feedback": "給學生的簡短中英文評語（說明為何通過，或為何不符）"
        }}
        """

        result = None
        used_model = None
        error_logs = []

        with st.spinner("AI 裁判比對特徵中... Verifying..."):
            for model_name in MODEL_FALLBACK_LIST:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[img_for_ai, prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                    result = json.loads(clean_text)
                    used_model = model_name
                    break
                except Exception as e:
                    error_logs.append(f"{model_name}: {e}")
                    time.sleep(1)

        if result is None:
            st.warning("⏳ 所有 AI 裁判目前都在塞車中，請等 10 秒後再按一次「提交」！")
            with st.expander("給老師看的錯誤紀錄"):
                st.caption(f"本次嘗試的模型清單：{MODEL_FALLBACK_LIST}")
                for log in error_logs:
                    st.caption(log)
            st.stop()

        # 5. 判定過關並更新集點表
        if result.get("is_match"):
            progress[team][target_species] = True
            pts = TARGETS[target_species]["points"]
            thumb = img_for_ai.copy()
            thumb.thumbnail((400, 400))
            gallery.insert(0, {
                "team": team,
                "species": target_species,
                "points": pts,
                "image": thumb,
                "feedback": result.get("feedback", "")
            })
            st.success(f"🎉 驗證通過！{team} 成功解鎖【{target_species.split(' ')[0]}】（+{pts} 分）")
            st.balloons()
            st.info(f"🤖 AI 評語：{result.get('feedback', '')}")
            st.caption(f"（本次由 `{used_model}` 完成鑑定）")
            st.button("🔄 刷新上方計分板")
        else:
            st.error(f"❌ 驗證未通過：AI 認為這不是【{target_species.split(' ')[0]}】。")
            st.info(f"🤖 AI 評語：{result.get('feedback', '')}")

# 6. 戰利品照片牆
st.divider()
with st.expander(f"🖼️ 即時過關照片牆（目前共 {len(gallery)} 筆）", expanded=False):
    if not gallery:
        st.caption("目前還沒有組別解鎖物種，快去尋找第一隻螃蟹吧！")
    else:
        for item in gallery:
            st.markdown(f"**{item['team']}** 解鎖了 **{item['species']}**")
            st.image(item["image"], width=300)
            st.caption(item["feedback"])
            st.markdown("---")
