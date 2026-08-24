import streamlit as st
import pandas as pd
import re
import io
import os
from pypdf import PdfReader

st.set_page_config(page_title="ระบบจัดการข้อมูลสินค้าตามโซน", layout="wide")

# ซ่อนปุ่มกากบาทของตัวอัปโหลดไฟล์ด้วย CSS
st.markdown("""
<style>
button[aria-label="Delete"] {
    display: none !important;
}
div[data-testid="stFileUploaderDeleteBtn"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

DB_FILE = "database_inventory.csv"

# รายการโซนทั้งหมด 27 โซน
ALL_ZONES = [
    "AA", "AB", "BB", "CC", "DD", "EE", "FF", "GG", 
    "IA", "IB", "IC", "JJ", "KK", "LL", "MA", "MB", 
    "MC", "MM", "NN", "PP", "QQ", "RR", "ST", "TT", 
    "UU", "XX", "YY"
]

def load_database():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE, dtype=str)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_database(df):
    df.to_csv(DB_FILE, index=False)

def format_tag_value(val):
    s = str(val).strip()
    if not s or s.lower() in ["nan", "none", "-", ""]:
        return "{ทั่วไป}"
    # ถ้ามีวงเล็บอยู่แล้ว
    if s.startswith("{") and s.endswith("}"):
        return s
    # ดึงค่าจากข้างในถ้ามีวงเล็บ
    m = re.search(r'[\{\[\(](.*?)[\}\]\)]', s)
    if m:
        return f"{{{m.group(1).strip()}}}"
    return f"{{{s}}}"

def parse_tag_and_clean_name(raw_text):
    text = str(raw_text).replace("•", "").strip()
    m_curly = re.search(r'\{([^}]+)\}', text)
    if m_curly:
        tag_val = m_curly.group(1).strip()
        cleaned_name = re.sub(r'\{[^}]+\}', '', text).strip()
        return f"{{{tag_val}}}", cleaned_name
    
    m_square = re.search(r'\[([^\]]+)\]', text)
    if m_square:
        tag_val = m_square.group(1).strip()
        cleaned_name = re.sub(r'\[[^\]]+\]', '', text).strip()
        return f"{{{tag_val}}}", cleaned_name
        
    return "{ทั่วไป}", text

def extract_fields_from_text(text, source_name, target_zone):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_name = m[3].strip()
        tag, clean_name = parse_tag_and_clean_name(raw_name)
        if m[4]:
            tag = f"{{{m[4].strip()}}}"
        extracted_zone = m[9].strip() if m[9] else target_zone
        barcode = str(m[1]).strip()
        data.append({
            "#": m[0],
            "รหัสสินค้า": barcode,
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": clean_name,
            "แท็ก {Tag}": tag,
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": extracted_zone.upper(),
            "คงเหลือ": str(m[6]).strip() if m[6] else "0",
            "สถานะ": m[7] if m[7] else "ปกติ",
            "ชื่อไฟล์ที่มา": source_name
        })
    return pd.DataFrame(data)

def clean_and_prepare_df(raw_df, source_name, target_zone):
    df = raw_df.copy()
    
    # 1. โซน
    zone_col = next((c for c in df.columns if "โซน" in str(c)), None)
    if zone_col:
        df["โซน"] = df[zone_col].astype(str).str.replace("โซน", "", regex=False).str.replace(":", "", regex=False).str.strip().str.upper()
    else:
        df["โซน"] = target_zone.upper()
        
    # 2. รหัสสินค้า
    barcode_col = next((c for c in df.columns if "รหัสสินค้า" in str(c) or str(c).strip() == "รหัส" or "บาร์โค้ด" in str(c)), None)
    if barcode_col:
        df["รหัสสินค้า"] = df[barcode_col].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    elif len(df.columns) > 2:
        df["รหัสสินค้า"] = df.iloc[:, 2].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

    # 3. รหัสรอง
    sub_col = next((c for c in df.columns if "รหัสรอง" in str(c)), None)
    if sub_col:
        df["รหัสรอง"] = df[sub_col].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    elif len(df.columns) > 3:
        df["รหัสรอง"] = df.iloc[:, 3].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

    # 4. ยอดคงเหลือ
    stock_col = next((c for c in df.columns if "คงเหลือ" in str(c)), None)
    if stock_col:
        df["คงเหลือ"] = df[stock_col].astype(str).str.replace(":", "", regex=False).str.strip()
    elif len(df.columns) > 1:
        df["คงเหลือ"] = df.iloc[:, 1].astype(str).str.replace(":", "", regex=False).str.strip()

    # 5. แท็ก {Tag} (อ่านจากคอลัมน์ แท็ก {Tag} โดยตรงเป็นหลัก)
    tag_col = next((c for c in df.columns if "แท็ก" in str(c) or "tag" in str(c).lower()), None)
    name_col = next((c for c in df.columns if any(k in str(c) for k in ["ชื่อ", "รายละ", "ยศ", "รายการ"])), None)
    if name_col is None and len(df.columns) > 4:
        name_col = df.columns[4]

    if tag_col:
        df["แท็ก {Tag}"] = df[tag_col].apply(format_tag_value)
        if name_col:
            df["ชื่อรายการสินค้า"] = df[name_col].astype(str).str.replace("•", "").strip()
        else:
            df["ชื่อรายการสินค้า"] = "-"
    elif name_col:
        parsed_results = df[name_col].apply(parse_tag_and_clean_name)
        df["แท็ก {Tag}"] = [res[0] for res in parsed_results]
        df["ชื่อรายการสินค้า"] = [res[1] for res in parsed_results]
    else:
        df["แท็ก {Tag}"] = "{ทั่วไป}"
        df["ชื่อรายการสินค้า"] = "-"

    if "จำนวนสั่งล่าสุด" not in df.columns:
        df["จำนวนสั่งล่าสุด"] = "0"
    if "สถานะ" not in df.columns:
        df["สถานะ"] = "ปกติ"
    if "หน่วยนับ" not in df.columns:
        df["หน่วยนับ"] = "-"
        
    df["ชื่อไฟล์ที่มา"] = source_name
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    existing_cols = [c for c in standard_cols if c in df.columns]
    return df[existing_cols]

def is_negative_stock(val):
    s = str(val).strip().replace(":", "")
    if s.startswith("-"):
        return True
    try:
        num = float(s)
        return num < 0
    except ValueError:
        return False

def render_product_cards(items_df, current_zone, is_problem=False):
    cols = st.columns(3)
    for idx, row in items_df.iterrows():
        barcode = str(row.get("รหัสสินค้า", "")).strip()
        sub_code = str(row.get("รหัสรอง", "")).strip()
        name = str(row.get("ชื่อรายการสินค้า", "")).strip()
        qty = row.get("จำนวนสั่งล่าสุด", 0)
        stock = row.get("คงเหลือ", 0)
        
        img_url = f"https://tkkonlineshop.com/images/products/{barcode}.jpg"
        web_link = f"https://tkkonlineshop.com/products/{barcode}"
        
        with cols[idx % 3]:
            with st.container(border=True):
                st.image(
                    img_url, 
                    caption=f"รหัส: {barcode}", 
                    use_container_width=True
                )
                st.markdown(f"**{name}**")
                st.caption(f"รหัสสินค้า: `{barcode}` | โซน: `{current_zone}`")
                st.markdown(f"📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                st.code(sub_code, language="text")
                if is_problem:
                    st.markdown(f"🚨 **คงเหลือ:** :red[{stock}] | 🛒 **สั่งล่าสุด:** {qty}")
                else:
                    st.markdown(f"📦 **คงเหลือ:** {stock} | 🛒 **สั่งล่าสุด:** {qty}")
                st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)

if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- แถบเมนูด้านซ้าย (Sidebar) ---
with st.sidebar:
    st.header("📍 โซนสินค้า")
    selected_zone = st.selectbox("เลือกโซนที่ต้องการเข้าดู:", options=ALL_ZONES)
    
    st.divider()
    st.subheader(f"⚙️ การจัดการข้อมูล [โซน {selected_zone}]")
    
    # เพิ่มไฟล์ข้อมูลเข้าโซน
    with st.expander(f"📥 เพิ่มไฟล์ข้อมูลเข้าโซน {selected_zone}", expanded=False):
        uploaded_files = st.file_uploader(
            f"เลือกไฟล์สำหรับโซน {selected_zone} (PDF, CSV, XLSX)", 
            type=["pdf", "csv", "xlsx"], 
            accept_multiple_files=True,
            key=f"uploader_{selected_zone}_{st.session_state.uploader_key}"
        )
        
        if uploaded_files:
            preview_dfs = []
            for u_file in uploaded_files:
                try:
                    if u_file.name.endswith(".pdf"):
                        reader = PdfReader(u_file)
                        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])
                        t_df = extract_fields_from_text(full_text, u_file.name, selected_zone)
                    elif u_file.name.endswith(".csv"):
                        t_df = clean_and_prepare_df(pd.read_csv(u_file), u_file.name, selected_zone)
                    elif u_file.name.endswith(".xlsx"):
                        t_df = clean_and_prepare_df(pd.read_excel(u_file), u_file.name, selected_zone)
                    
                    if not t_df.empty:
                        t_df["โซน"] = t_df["โซน"].replace({"": selected_zone, "-": selected_zone, "NAN": selected_zone}).fillna(selected_zone)
                        preview_dfs.append(t_df)
                except Exception as e:
                    st.error(f"ไฟล์ {u_file.name} ผิดพลาด: {e}")
            
            if preview_dfs:
                combined_new_df = pd.concat(preview_dfs, ignore_index=True)
                st.info(f"เตรียมพร้อมบันทึก: {len(combined_new_df)} รายการ")
                
                if st.button(f"💾 ยืนยันบันทึกเข้าโซน {selected_zone}", type="primary"):
                    if st.session_state.current_df.empty:
                        st.session_state.current_df = combined_new_df
                    else:
                        st.session_state.current_df = pd.concat([st.session_state.current_df, combined_new_df], ignore_index=True)
                        if "รหัสสินค้า" in st.session_state.current_df.columns:
                            st.session_state.current_df.drop_duplicates(subset=["รหัสสินค้า"], keep="last", inplace=True)
                    
                    save_database(st.session_state.current_df)
                    st.session_state.uploader_key += 1
                    st.success(f"✅ บันทึกข้อมูลเข้าโซน {selected_zone} เรียบร้อย!")
                    st.rerun()

    # ลบไฟล์ออกจากโซน
    with st.expander(f"📁 ลบข้อมูลไฟล์ในโซน {selected_zone}", expanded=False):
        df_all = st.session_state.current_df
        if not df_all.empty and "โซน" in df_all.columns and "ชื่อไฟล์ที่มา" in df_all.columns:
            zone_files = df_all[df_all["โซน"] == selected_zone]["ชื่อไฟล์ที่มา"].dropna().unique().tolist()
            if zone_files:
                selected_remove_file = st.selectbox("เลือกไฟล์ที่ต้องการลบ:", options=zone_files)
                if st.button("🗑️ ยืนยันลบไฟล์นี้"):
                    condition = (st.session_state.current_df["ชื่อไฟล์ที่มา"] == selected_remove_file) & (st.session_state.current_df["โซน"] == selected_zone)
                    st.session_state.current_df = st.session_state.current_df[~condition]
                    save_database(st.session_state.current_df)
                    st.success(f"ลบข้อมูลสำเร็จ")
                    st.rerun()
            else:
                st.caption(f"ยังไม่มีไฟล์ข้อมูลในโซน {selected_zone}")
        else:
            st.caption("ยังไม่มีข้อมูลในระบบ")

    st.divider()
    st.subheader("⚠️ ตรวจสอบรายการ")
    view_mode = st.radio("เลือกมุมมองที่ต้องการดู:", ["📦 รายการสินค้าปกติ", "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)"])

# --- หน้าแดชบอร์ดหลัก ---
df_all = st.session_state.current_df

if not df_all.empty and "โซน" in df_all.columns:
    df_zone = df_all[df_all["โซน"] == selected_zone].reset_index(drop=True)
else:
    df_zone = pd.DataFrame()

# ================= 1. มุมมองสินค้าที่มีปัญหา =================
if view_mode == "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title(f"⚠️ สินค้าที่มีปัญหา [คงเหลือติดลบ -] : โซน {selected_zone}")
    
    if not df_zone.empty and "คงเหลือ" in df_zone.columns:
        mask_negative = df_zone["คงเหลือ"].apply(is_negative_stock)
        problem_df = df_zone[mask_negative].reset_index(drop=True)
        
        if not problem_df.empty:
            st.error(f"🚨 พบสินค้าคงเหลือติดลบทั้งหมด **{len(problem_df)} รายการ** ในโซน {selected_zone}")
            
            prob_tags = sorted(list(problem_df["แท็ก {Tag}"].dropna().unique()))
            tag_options = ["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + prob_tags
            selected_prob_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่มีปัญหา:", options=tag_options)
            
            if selected_prob_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                for tag in prob_tags:
                    group_prob_df = problem_df[problem_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                    with st.expander(f"🚨 แท็ก: **{tag}** (รวม {len(group_prob_df)} รายการ)", expanded=True):
                        render_product_cards(group_prob_df, selected_zone, is_problem=True)
            else:
                filtered_prob_df = problem_df[problem_df["แท็ก {Tag}"] == selected_prob_tag].reset_index(drop=True)
                st.write(f"พบ **{len(filtered_prob_df)} รายการ** ที่ติดลบ ในแท็ก `{selected_prob_tag}`")
                render_product_cards(filtered_prob_df, selected_zone, is_problem=True)

            st.divider()
            st.subheader(f"📋 ตารางรายการสินค้าที่มีปัญหา [โซน {selected_zone}]")
            display_prob_df = problem_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
            st.dataframe(display_prob_df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                display_prob_df.to_excel(writer, sheet_name=f"ปัญหา_{selected_zone}", index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดรายการสินค้ามีปัญหา โซน {selected_zone} (.xlsx)",
                data=output.getvalue(),
                file_name=f"สินค้ามีปัญหา_โซน_{selected_zone}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success(f"🎉 ยอดเยี่ยม! ไม่พบสินค้าคงเหลือติดลบในโซน {selected_zone}")
    else:
        st.info(f"👈 โซน {selected_zone} ยังไม่มีข้อมูลสินค้า")

# ================= 2. มุมมองสินค้าปกติ =================
else:
    st.title(f"📦 สินค้าประจำโซน : {selected_zone}")

    if not df_zone.empty:
        st.subheader("🖼️ แสดงสินค้าและรูปภาพตามกลุ่มแท็ก")
        
        if "แท็ก {Tag}" in df_zone.columns:
            tag_list = sorted(list(df_zone["แท็ก {Tag}"].dropna().unique()))
            tag_options = ["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + tag_list
            selected_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่ต้องการดู:", options=tag_options)
            
            if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                for tag in tag_list:
                    group_df = df_zone[df_zone["แท็ก {Tag}"] == tag].reset_index(drop=True)
                    with st.expander(f"📦 แท็ก: **{tag}** (รวม {len(group_df)} รายการ)", expanded=True):
                        render_product_cards(group_df, selected_zone, is_problem=False)
            else:
                filtered_df = df_zone[df_zone["แท็ก {Tag}"] == selected_tag].reset_index(drop=True)
                st.write(f"พบ **{len(filtered_df)} รายการ** ในแท็ก `{selected_tag}` (โซน {selected_zone})")
                render_product_cards(filtered_df, selected_zone, is_problem=False)

        st.divider()

        st.subheader(f"📋 ตารางรายการข้อมูล [โซน {selected_zone}]")
        display_df = df_zone.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
        st.dataframe(display_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            display_df.to_excel(writer, sheet_name=f"โซน_{selected_zone}", index=False)
        
        st.download_button(
            label=f"📥 ดาวน์โหลดไฟล์ Excel โซน {selected_zone} (.xlsx)",
            data=output.getvalue(),
            file_name=f"ข้อมูลสินค้า_โซน_{selected_zone}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info(f"👈 โซน **{selected_zone}** ยังไม่มีข้อมูล คลิกที่เมนูด้านซ้าย **'📥 เพิ่มไฟล์ข้อมูลเข้าโซน {selected_zone}'** เพื่ออัปโหลดและกดบันทึก")
