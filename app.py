from flask import Flask, jsonify, render_template
import pandas as pd
import os, re, glob
from functools import lru_cache

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_XLSX = os.path.join(APP_ROOT, 'data', 'species.xlsx')

# Photos directories
for cand in (os.path.join(APP_ROOT, 'static', 'photos'),
             os.path.join(APP_ROOT, 'static', 'Photos')):
    if os.path.isdir(cand):
        PHOTO_ROOT = cand
        break
else:
    PHOTO_ROOT = os.path.join(APP_ROOT, 'static', 'photos')

# Icons root
ICONS_ROOT = os.path.join(APP_ROOT, 'static', 'Icons')
ICON_DIRS = {
    'species': os.path.join(ICONS_ROOT, 'Species'),
    'leaf':    os.path.join(ICONS_ROOT, 'Leaf'),
    'fruit':   os.path.join(ICONS_ROOT, 'Fruit'),
}

ALLOWED_IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

app = Flask(__name__)

REQUIRED_COLS = [
    'Sr No','Scientific name','Etymology','Common name','Habitat','Phenology',
    'Identification Characters','Leaf type','Fruit Type','Seed Germination','Pest'
]

LEAF_TOPLEVEL = ['Simple', 'Pinnately compound', 'Palmately compound']
LEAF_SUBTYPES = ['single', 'double']  # add 'triple' if needed


# ---------------- Utilities ----------------
def _norm_key(s: str) -> str:
    if not isinstance(s, str):
        s = str(s or '')
    s = s.strip().lower()
    s = re.sub(r'[_\-]+', ' ', s)
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _build_icon_index(folder_path: str):
    out = {}
    if not os.path.isdir(folder_path):
        return out
    for fname in os.listdir(folder_path):
        full = os.path.join(folder_path, fname)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_IMG_EXT:
            continue
        base = os.path.splitext(fname)[0]
        out[_norm_key(base)] = '/' + os.path.relpath(full, APP_ROOT).replace('\\', '/')
    return out

SPECIES_ICON_INDEX = _build_icon_index(ICON_DIRS['species'])
LEAF_ICON_INDEX    = _build_icon_index(ICON_DIRS['leaf'])
FRUIT_ICON_INDEX   = _build_icon_index(ICON_DIRS['fruit'])


@lru_cache(maxsize=1024)
def slugify(name: str) -> str:
    if not isinstance(name, str):
        name = str(name)
    s = name.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip('-')
    return s


def _leaf_category_and_subtype(leaf_type_value: str):
    if not isinstance(leaf_type_value, str):
        return (None, None)
    t = leaf_type_value.strip()
    tl = t.lower()
    if tl.startswith('simple') or 'simple' in tl:
        return ('Simple', None)
    if tl.startswith('pinnately') or 'pinnate' in tl or 'compound' in tl:
        m = re.search(r"\((single|double|triple)\)", t, re.IGNORECASE)
        subtype = (m.group(1) if m else None)
        subtype = subtype.lower() if subtype else None
        return ('Pinnately compound', subtype)
    if tl.startswith('palmately') or 'palmate' in tl:
        return ('Palmately compound', None)
    return (None, None)


def _pick_species_icon(scientific: str, common: str):
    candidates = [scientific or '', common or '']
    for c in list(candidates):
        c2 = re.sub(r'\(.*?\)', '', c).strip()
        if c2 and c2 not in candidates:
            candidates.append(c2)
    for name in candidates:
        key = _norm_key(name)
        if key in SPECIES_ICON_INDEX:
            return SPECIES_ICON_INDEX[key]
    return None


def _pick_leaf_icon(toplevel: str, subtype: str):
    if (toplevel or '').lower().startswith('simple'):
        keys = ['simple leaf', 'simple']
    elif (toplevel or '').lower().startswith('pinnately'):
        if subtype == 'single':
            keys = ['single compound', 'pinnately single', 'pinnately compound single']
        elif subtype == 'double':
            keys = ['double compound', 'pinnately double', 'pinnately compound double']
        else:
            keys = ['pinnately compound', 'compound']
    elif (toplevel or '').lower().startswith('palmately'):
        keys = ['palmately compound', 'palmate', 'palmately']
    else:
        keys = []
    for k in keys:
        nk = _norm_key(k)
        if nk in LEAF_ICON_INDEX:
            return LEAF_ICON_INDEX[nk]
    return None


def _pick_fruit_icon(fruit_type: str):
    if not fruit_type:
        return None
    nk = _norm_key(fruit_type)
    if nk in FRUIT_ICON_INDEX:
        return FRUIT_ICON_INDEX[nk]
    for alias in ('pod', 'capsule', 'drupe', 'other'):
        if nk == alias and alias in FRUIT_ICON_INDEX:
            return FRUIT_ICON_INDEX[alias]
    return None


def load_and_process_data():
    if os.path.exists(DATA_XLSX):
        df = pd.read_excel(DATA_XLSX, sheet_name=0)
    else:
        df = pd.DataFrame(columns=REQUIRED_COLS)

    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ''

    df = df[~df['Scientific name'].isna() & (df['Scientific name'].astype(str).str.strip() != '')].copy()

    records_list, records_dict = [], {}
    for _, row in df.iterrows():
        sci = str(row['Scientific name']).strip()
        com = str(row.get('Common name', '')).strip()
        rec_id = slugify(sci)
        leaf_raw = str(row.get('Leaf type', '')).strip()
        leaf_top, leaf_sub = _leaf_category_and_subtype(leaf_raw)

        # photos
        photo_dir = os.path.join(PHOTO_ROOT, rec_id)
        photos = []
        if os.path.isdir(photo_dir):
            for path in sorted(glob.glob(os.path.join(photo_dir, '*'))):
                ext = os.path.splitext(path)[1].lower()
                if ext in ALLOWED_IMG_EXT:
                    photos.append('/' + os.path.relpath(path, APP_ROOT).replace('\\', '/'))

        # icons
        species_icon = _pick_species_icon(sci, com)
        leaf_icon = _pick_leaf_icon(leaf_top, leaf_sub)
        fruit_raw = str(row.get('Fruit Type', '')).strip()
        fruit_icon = _pick_fruit_icon(fruit_raw)

        rec = {
            'id': rec_id,
            'sr_no': row.get('Sr No', ''),
            'scientific_name': sci,
            'etymology': str(row.get('Etymology', '')).strip(),
            'common_name': com,
            'habitat': str(row.get('Habitat', '')).strip(),
            'phenology': str(row.get('Phenology', '')).strip(),
            'identification': str(row.get('Identification Characters', '')).strip(),
            'leaf_type_raw': leaf_raw,
            'leaf_category': leaf_top,
            'leaf_subtype': leaf_sub,
            'fruit_type': fruit_raw,
            'seed_germination': str(row.get('Seed Germination', '')).strip(),
            'pest': str(row.get('Pest', '')).strip(),
            'photos': photos,
            'icons': {'species': species_icon, 'leaf': leaf_icon, 'fruit': fruit_icon}
        }
        records_list.append(rec)
        records_dict[rec_id] = rec

    fruit_types = sorted({(r['fruit_type'] or '').strip() for r in records_list if (r['fruit_type'] or '').strip()})

    leaf_chip_icons = {lt: _pick_leaf_icon(lt, None) for lt in LEAF_TOPLEVEL}
    fruit_chip_icons = {ft: _pick_fruit_icon(ft) for ft in fruit_types}

    filters = {
        'leaf_toplevel': LEAF_TOPLEVEL,
        'leaf_subtypes_possible': LEAF_SUBTYPES,
        'fruit_types': fruit_types,
        'leaf_chip_icons': leaf_chip_icons,
        'fruit_chip_icons': fruit_chip_icons
    }
    return records_list, records_dict, filters


SPECIES_LIST, SPECIES_DICT, FILTERS = load_and_process_data()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/species')
def api_species():
    return jsonify({'items': SPECIES_LIST, 'filters': FILTERS})


@app.route('/api/species/<rec_id>')
def api_species_one(rec_id):
    rec = SPECIES_DICT.get(rec_id)
    if rec:
        return jsonify(rec)
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
