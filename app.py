import streamlit as st
import pandas as pd
import re
import io
import os
from pypdf import PdfReader

st.set_page_config(page_title="ระบบจัดการจำนวนสินค้าตามโซน", layout="wide")

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

def extract_fields_from_text(text, source_name, target_zone):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_tag = m[4].strip() if m[4] else ""
        extracted_zone = m[9].strip() if m[9] else target_zone
        barcode = str(m[1]).strip()
        data.append({
            "#": m[0],
            "รหัสสินค้า": barcode,
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": m[3].strip(),
            "แท็ก {Tag}": f"{{{raw_tag}}}" if raw_tag else "{ทั่วไป}",
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": extracted_zone,
            "คงเหลือ": str(m[6]).strip() if m[6] else "0",
            "สถานะ": m[7] if m[7] else "ปกติ",
            "ชื่อไฟล์ที่มา": source_name
        })
    return pd.DataFrame(data)

def clean_and_prepare_df(raw_df, source_name, target_zone):
    df = raw_df.copy()
    for col in df.columns:
        if "รหัสสินค้า" in str(col) or str(col) == "รหัส":
            df["รหัสสินค้า"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if "รหัสรอง" in str(col):
            df["รหัสรอง"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
    if "แท็ก {Tag}" not in df.columns:
        name_col = next((c for c in df.columns if "ชื่อ" in str(c) or "รายละ" in str(c)), df.columns[3] if len(df.columns) > 3 else df.columns[0])
        def get_tag(x):
            m = re.search(r'\{([^}]+)\}', str(x))
            return f"{{{m.group(1).strip()}}}" if m else "{ทั่วไป}"
        def get_name(x):
            return re.sub(r'\{[^}]+\}', '', str(x)).strip()
            
        df["แท็ก {Tag}"] = df[name_col].apply(get_tag)
        df["ชื่อรายการสินค้า"] = df[name_col].apply(get_name)
    else:
        df["แท็ก {Tag}"] = df["แท็ก {Tag}"].fillna("{ทั่วไป}").astype(str).str.strip()
    
    for c in df.columns:
        if "สั่ง" in str(c):
            df["จำนวนสั่งล่าสุด"] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int).astype(str)
        if "คงเหลือ" in str(c):
            df["คงเหลือ"] = df[c].astype(str).str.strip()
            
    if "โซน" not in df.columns:
        df["โซน"] = target_zone
    else:
        df["โซน"] = df["โซน"].fillna(target_zone).astype(str).str.strip()
        
    df["ชื่อไฟล์ที่มา"] = source_name
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    existing_cols = [c for c in standard_cols if c in df.columns]
    return df[existing_cols]

# ฟังก์ชันตรวจสอบว่าค่าคงเหลือติดลบหรือไม่
def is_negative_stock(val):
    s = str(val).strip()
    if s.startswith("-"):
        return True
    try:
        num = float(s)
        return num < 0
    except ValueError:
        return False

if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- แถบเมนูด้านซ้าย (Sidebar) ---
with st.sidebar:
    st.header("📊 จำนวนสินค้า")
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
                        t_df["โซน"] = t_df["โซน"].replace({"": selected_zone, "-": selected_zone}).fillna(selected_zone)
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

    # --- ฟังก์ชันสินค้าที่มีปัญหา (อยู่ใต้การจัดการข้อมูล) ---
    st.subheader("⚠️ ตรวจสอบรายการ")
    view_mode = st.radio("เลือกมุมมองที่ต้องการดู:", ["📦 รายการสินค้าปกติ", "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)"])

# --- การประมวลผลข้อมูลหน้าแดชบอร์ด ---
df_all = st.session_state.current_df

if not df_all.empty and "โซน" in df_all.columns:
    df_zone = df_all[df_all["โซน"] == selected_zone].reset_index(drop=True)
else:
    df_zone = pd.DataFrame()

# ================= 1. มุมมองสินค้าที่มีปัญหา (คงเหลือติดลบ) =================
if view_mode == "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title(f"⚠️ สินค้าที่มีปัญหา [คงเหลือติดลบ -] : โซน {selected_zone}")
    
    if not df_zone.empty and "คงเหลือ" in df_zone.columns:
        # กรองเฉพาะรายการที่คงเหลือมีเครื่องหมายลบ (-) นำหน้า
        mask_negative = df_zone["คงเหลือ"].apply(is_negative_stock)
        problem_df = df_zone[mask_negative].reset_index(drop=True)
        
        if not problem_df.empty:
            st.error(f"🚨 พบสินค้าคงเหลือติดลบทั้งหมด **{len(problem_df)} รายการ** ในโซน {selected_zone}")
            
            # ดึงแท็กเฉพาะกลุ่มที่มีสินค้าติดลบ
            prob_tags = sorted(list(problem_df["แท็ก {Tag}"].dropna().unique()))
            selected_prob_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่มีปัญหา:", options=["แสดงทุกกลุ่มแท็ก"] + prob_tags)
            
            display_prob_tags = prob_tags if selected_prob_tag == "แสดงทุกกลุ่มแท็ก" else [selected_prob_tag]
            
            for tag in display_prob_tags:
                tag_prob_df = problem_df[problem_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                
                with st.expander(f"🚨 แท็ก: **{tag}** (ติดลบ {len(tag_prob_df)} รายการ)", expanded=True):
                    cols = st.columns(3)
                    for idx, row in tag_prob_df.iterrows():
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
                                st.caption(f"รหัสสินค้า: `{barcode}` | โซน: `{selected_zone}`")
                                st.markdown(f"📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                                st.code(sub_code, language="text")
                                st.markdown(f"🚨 **คงเหลือ:** :red[{stock}] | 🛒 **สั่งล่าสุด:** {qty}")
                                st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)

            st.divider()
            st.subheader(f"📋 ตารางรายการสินค้าที่มีปัญหา [โซน {selected_zone}]")
            display_prob_df = problem_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
            st.dataframe(display_prob_df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                display_prob_df.to_excel(writer, sheet_name=f"ปัญหา_โซน_{selected_zone}", index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดรายการสินค้าที่มีปัญหา โซน {selected_zone} (.xlsx)",
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
    st.title(f"📦 จำนวนสินค้าประจำโซน : {selected_zone}")

    if not df_zone.empty:
        st.subheader("🏷️ สินค้าจัดกลุ่มตามแท็ก {Tag}")
        
        unique_tags = sorted(list(df_zone["แท็ก {Tag}"].dropna().unique()))
        selected_tag = st.selectbox("🔍 เลือกกลุ่มแท็กเพื่อแสดง:", options=["แสดงทุกกลุ่มแท็ก"] + unique_tags)
        
        display_tags = unique_tags if selected_tag == "แสดงทุกกลุ่มแท็ก" else [selected_tag]
        
        for tag in display_tags:
            group_df = df_zone[df_zone["แท็ก {Tag}"] == tag].reset_index(drop=True)
            
            with st.expander(f"📌 แท็ก: **{tag}** (รวม {len(group_df)} รายการ)", expanded=True):
                cols = st.columns(3)
                for idx, row in group_df.iterrows():
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
                            st.caption(f"รหัสสินค้า: `{barcode}` | โซน: `{selected_zone}`")
                            st.markdown(f"📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                            st.code(sub_code, language="text")
                            st.markdown(f"📦 **คงเหลือ:** {stock} | 🛒 **สั่งล่าสุด:** {qty}")
                            st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)

        st.divider()

        st.subheader(f"📋 ตารางข้อมูลสินค้าทั้งหมด [โซน {selected_zone}]")
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
