import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from io import BytesIO
from PIL import Image
import re

st.set_page_config(page_title="Blueprint Generator — Center Hall", layout="wide")

# -------------------- Helpers --------------------
def parse_room_changes(text):
    """
    Parses user input like:
      - 'Kitchen (Ground) 13x14 ft'  -> dimension change / add new room
      - 'Swap Pooja Room - Kitchen (Ground)' -> swap rooms
    """
    changes = {}
    swaps = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # ✅ Swap detection (both - and ↔)
        m_swap = re.search(r"Swap\s+(.+?)\s*(?:-|\u2194)\s*(.+?)\s*\((Ground|First|Floor\s*\d+)\)", line, re.IGNORECASE)
        if m_swap:
            room1 = m_swap.group(1).strip()
            room2 = m_swap.group(2).strip()
            floor = m_swap.group(3).strip().lower()
            swaps.append((floor, room1, room2))
            continue

        # ✅ Room add or update detection
        m = re.search(r"(.+?)\s*\((Ground|First|Floor\s*\d+)\)\s*(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s*ft", line, re.IGNORECASE)
        if m:
            room = m.group(1).strip()
            floor = m.group(2).strip().lower()
            w = float(m.group(3))
            h = float(m.group(4))
            changes.setdefault(floor, {})[room] = (w, h)

    return changes, swaps


def apply_room_changes(placements, changes_dict, swaps_list, floor_label):
    """Apply dimension changes, additions, and swaps to the given placements."""
    floor_key = floor_label.lower()

    # ✅ Apply add/update dimensions
    if floor_key in changes_dict:
        for room, (new_w, new_h) in changes_dict[floor_key].items():
            if room in placements:
                placements[room]['w'] = new_w
                placements[room]['h'] = new_h
            else:
                placements[room] = {'x': 0.0, 'y': 0.0, 'w': new_w, 'h': new_h}

    # ✅ Apply swaps (swap **names** in blueprint)
    for floor, r1, r2 in swaps_list:
        if floor == floor_key and r1 in placements and r2 in placements:
            placements[r1], placements[r2] = placements[r2], placements[r1]

    return placements


def fig_to_pil(fig, dpi=150):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=dpi, pad_inches=0.05)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    buf.close()
    plt.close(fig)
    return img

# -------------------- UI --------------------
st.sidebar.title("Blueprint Inputs")
total_sqft = st.sidebar.number_input("Total area (sqft) — informational", min_value=100, value=1200, step=50)
W = st.sidebar.number_input("Width (ft)", min_value=10.0, value=30.0, step=1.0)
H = st.sidebar.number_input("Breadth / Length (ft)", min_value=10.0, value=40.0, step=1.0)
floors = st.sidebar.selectbox("Number of floors (ground + ...)", options=[1, 2, 3, 4], index=2)

pref_text = st.sidebar.text_area(
    "Room changes / Additions / Swaps (one per line)\nExamples:\n"
    "Kitchen (Ground) 13x14 ft\n"
    "Game Room (Ground) 12x15 ft\n"
    "Swap Pooja Room - Kitchen (Ground)"
)

generate = st.sidebar.button("Generate Blueprint")

st.title("Auto Blueprint Generator")
st.markdown("""
Supports:
- **Dimension changes** (e.g., `Kitchen (Ground) 13x14 ft`)  
- **Add new rooms** (e.g., `Game Room (Ground) 12x15 ft`)  
- **Swap rooms** (e.g., `Swap Pooja Room - Kitchen (Ground)`)  
""")

# -------------------- Layout builders --------------------
def make_ground_layout(W, H, include_stair):
    placements = {}
    left_w = round(W * 0.23, 3)
    right_w = round(W * 0.30, 3)
    mid_w = W - left_w - right_w

    pooja_h = round(H * 0.22, 3)
    stair_h = round(H * 0.18, 3) if include_stair else 0.0
    bedroom_h = round(H - (pooja_h + stair_h), 3)

    placements['Pooja Room'] = {'x': 0.0, 'y': H - pooja_h, 'w': left_w, 'h': pooja_h}
    if include_stair:
        placements['Staircase'] = {'x': 0.0, 'y': H - pooja_h - stair_h, 'w': left_w, 'h': stair_h}
        placements['Bedroom'] = {'x': 0.0, 'y': 0.0, 'w': left_w, 'h': bedroom_h}
    else:
        placements['Bedroom'] = {'x': 0.0, 'y': 0.0, 'w': left_w, 'h': H - pooja_h}

    kitchen_h = round(H * 0.30, 3)
    living_h = round(H * 0.36, 3)
    placements['Kitchen'] = {'x': left_w + mid_w, 'y': H - kitchen_h, 'w': right_w, 'h': kitchen_h}
    placements['Living Room'] = {'x': left_w + mid_w, 'y': 0.0, 'w': right_w, 'h': living_h}
    remaining_h = H - (kitchen_h + living_h)
    placements['Bathroom'] = {'x': left_w + mid_w, 'y': living_h, 'w': right_w, 'h': remaining_h}

    placements['Center Hall'] = {'x': left_w, 'y': 0.0, 'w': mid_w, 'h': H}
    return placements

def make_upper_layout(W, H, floor_index, include_stair_here):
    placements = {}
    bal_h = round(H * 0.12, 3)
    bal_w = round(W * 0.9, 3)
    bal_x = round((W - bal_w) / 2.0, 3)
    placements['Balcony'] = {'x': bal_x, 'y': H - bal_h, 'w': bal_w, 'h': bal_h}

    bed_w = round(W / 3.0, 3)
    rem_h = H - bal_h
    bath_h = max(3.0, round(rem_h * 0.08, 3))
    bed_h = round(rem_h - bath_h, 3)

    for i in range(3):
        x = round(i * bed_w, 3)
        placements[f'AttachedBath{i+1}'] = {'x': x, 'y': 0.0, 'w': round(bed_w*0.9, 3), 'h': bath_h}
        placements[f'Bedroom{i+1}'] = {'x': x, 'y': bath_h, 'w': bed_w, 'h': bed_h}

    if include_stair_here:
        stair_w = round(W * 0.18, 3)
        placements['Staircase'] = {'x': 0.0, 'y': 0.0, 'w': stair_w, 'h': rem_h}

    return placements

# -------------------- Drawing --------------------
def draw_floor(W, H, placements, floor_label):
    ft_to_in = 0.25
    fig_w = max(6, W * ft_to_in)
    fig_h = max(6, H * ft_to_in)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect('equal')
    ax.axis('off')

    ax.add_patch(Rectangle((0, 0), W, H, fill=False, edgecolor='black', lw=4))

    for name, r in placements.items():
        x, y, w, h = r['x'], r['y'], r['w'], r['h']
        if name != "Center Hall":
            ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor='black', lw=3))

        cx = x + w / 2.0
        cy = y + h / 2.0
        ax.text(cx, cy + 0.2, name, ha='center', va='center', fontsize=9, weight='bold')
        ax.text(cx, cy - 0.2, f"{round(w,1)} × {round(h,1)} ft", ha='center', va='center', fontsize=8)

    ax.set_title(floor_label.capitalize(), fontsize=14, weight='bold')
    return fig

# -------------------- Main Flow --------------------
images = []
if generate:
    room_changes, swaps = parse_room_changes(pref_text)

    for idx in range(floors):
        if idx == 0:
            ground = make_ground_layout(W, H, include_stair=(floors >= 2))
            ground = apply_room_changes(ground, room_changes, swaps, "ground")
            fig = draw_floor(W, H, ground, "Ground")
        else:
            include_stair_here = (idx < floors - 1)
            up = make_upper_layout(W, H, floor_index=idx, include_stair_here=include_stair_here)
            floor_name = "first" if idx == 1 else f"floor {idx}"
            up = apply_room_changes(up, room_changes, swaps, floor_name)
            fig = draw_floor(W, H, up, floor_name)

        pil_img = fig_to_pil(fig, dpi=150)
        max_width = 800
        if pil_img.width > max_width:
            w_percent = (max_width / float(pil_img.width))
            h_size = int((float(pil_img.height) * float(w_percent)))
            pil_img = pil_img.resize((max_width, h_size), Image.Resampling.LANCZOS)

        images.append(pil_img)

    st.success("Blueprints generated — scroll to view floors below.")
    for idx, img in enumerate(images):
        st.image(img, caption=f"Floor {idx}")

    pdf_buf = BytesIO()
    images[0].save(pdf_buf, format='PDF', save_all=True, append_images=images[1:])
    pdf_buf.seek(0)
    st.sidebar.download_button("Download Blueprints (PDF)", data=pdf_buf, file_name="blueprints.pdf", mime="application/pdf")

else:
    st.info("Set inputs and click Generate Blueprint. Defaults: Width=30 ft, Breadth=40 ft, Floors=3.")
    preview = make_ground_layout(W, H, include_stair=(floors >= 2))
    room_changes, swaps = parse_room_changes(pref_text)
    preview = apply_room_changes(preview, room_changes, swaps, "ground")
    fig_preview = draw_floor(W, H, preview, "Preview Ground Floor")
    pil_preview = fig_to_pil(fig_preview, dpi=120)
    max_width = 800
    if pil_preview.width > max_width:
        w_percent = (max_width / float(pil_preview.width))
        h_size = int((float(pil_preview.height) * float(w_percent)))
        pil_preview = pil_preview.resize((max_width, h_size), Image.Resampling.LANCZOS)
    st.image(pil_preview)

st.markdown("---")
