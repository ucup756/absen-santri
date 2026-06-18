from flask import Blueprint, render_template, request, send_file, Response
from flask_login import login_required
from models import Santri, Pengaturan
import io, zipfile

kartu_bp = Blueprint('kartu', __name__)

KELAS_LIST = ['Kelas 1A','Kelas 1B','Kelas 2A','Kelas 2B',
              'Kelas 3A','Kelas 3B','Kelas 4A','Kelas 4B']

DPI = 300
W   = 638   # 54mm (tinggi KTP) → kartu portrait
H   = 1011  # 85.6mm


def _font(path, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _buat_kartu(santri) -> bytes:
    """Kartu sederhana: logo + nama pesantren di atas, QR besar di tengah, nama santri di bawah."""
    from PIL import Image, ImageDraw
    import qrcode as qrlib
    import base64

    FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
    FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'

    C_BG    = (255, 255, 255)
    C_NAVY  = (30,  58,  138)
    C_GOLD  = (200, 150,  20)
    C_DARK  = (17,  24,   39)
    C_GRAY  = (100, 116, 139)

    # Ambil pengaturan
    nama_pesantren = Pengaturan.get('nama_pesantren', 'Pesantren Digital')
    tagline        = Pengaturan.get('tagline', 'Sistem Absensi Santri')
    logo_b64       = Pengaturan.get('logo_base64', '')

    img  = Image.new('RGB', (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    # ── Strip atas navy ───────────────────────────────────
    STRIP_H = 160
    draw.rectangle([0, 0, W, STRIP_H], fill=C_NAVY)
    # Aksen garis emas bawah strip
    draw.rectangle([0, STRIP_H, W, STRIP_H + 6], fill=C_GOLD)

    # ── Logo pesantren ────────────────────────────────────
    LOGO_SIZE = 80
    LOGO_Y    = (STRIP_H - LOGO_SIZE) // 2
    LOGO_X    = 28

    if logo_b64:
        try:
            # logo_b64 format: "data:image/png;base64,<data>"
            raw = logo_b64.split(',', 1)[-1]
            logo_bytes = base64.b64decode(raw)
            logo_img = Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
            logo_img = logo_img.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
            img.paste(logo_img, (LOGO_X, LOGO_Y), logo_img)
        except Exception:
            _draw_logo_placeholder(draw, LOGO_X, LOGO_Y, LOGO_SIZE, C_GOLD)
    else:
        _draw_logo_placeholder(draw, LOGO_X, LOGO_Y, LOGO_SIZE, C_GOLD)

    # ── Teks header ───────────────────────────────────────
    TX = LOGO_X + LOGO_SIZE + 16
    fn1 = _font(FONT_BOLD,    34)
    fn2 = _font(FONT_REGULAR, 22)
    draw.text((TX, LOGO_Y + 4),  nama_pesantren, font=fn1, fill=(255, 255, 255))
    draw.text((TX, LOGO_Y + 44), tagline,        font=fn2, fill=(180, 200, 255))

    # ── QR Code ───────────────────────────────────────────
    QR_SIZE  = 480   # px
    QR_Y     = STRIP_H + 60

    qr = qrlib.QRCode(
        version=3, box_size=14, border=2,
        error_correction=qrlib.constants.ERROR_CORRECT_H
    )
    qr.add_data(santri.nis or 'UNKNOWN')
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=C_NAVY, back_color='white').convert('RGB')
    qr_img = qr_img.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

    QX = (W - QR_SIZE) // 2
    # Border tipis abu di sekitar QR
    pad = 8
    draw.rounded_rectangle(
        [QX - pad, QR_Y - pad, QX + QR_SIZE + pad, QR_Y + QR_SIZE + pad],
        radius=12, fill=(245, 247, 250), outline=(220, 226, 235), width=2
    )
    img.paste(qr_img, (QX, QR_Y))

    # ── NIS kecil di bawah QR ─────────────────────────────
    NIS_Y = QR_Y + QR_SIZE + pad + 12
    fnis  = _font(FONT_REGULAR, 26)
    nis_txt = santri.nis or '-'
    tw = draw.textlength(nis_txt, font=fnis)
    draw.text(((W - tw) // 2, NIS_Y), nis_txt, font=fnis, fill=C_GRAY)

    # ── Nama santri ───────────────────────────────────────
    NAMA_Y = NIS_Y + 40
    fnama  = _font(FONT_BOLD, 46)

    nama = santri.nama
    # Potong kalau terlalu panjang
    while draw.textlength(nama, font=fnama) > W - 40 and len(nama) > 4:
        nama = nama[:-1]
    if nama != santri.nama:
        nama = nama[:-1] + '…'

    tw = draw.textlength(nama, font=fnama)
    draw.text(((W - tw) // 2, NAMA_Y), nama, font=fnama, fill=C_DARK)

    # ── Kelas ─────────────────────────────────────────────
    KELAS_Y = NAMA_Y + 60
    fkelas  = _font(FONT_REGULAR, 28)
    kelas_txt = santri.kelas or ''
    if kelas_txt:
        tw = draw.textlength(kelas_txt, font=fkelas)
        draw.text(((W - tw) // 2, KELAS_Y), kelas_txt, font=fkelas, fill=C_GRAY)

    # ── Strip bawah navy ──────────────────────────────────
    draw.rectangle([0, H - 60, W, H], fill=C_NAVY)
    draw.rectangle([0, H - 66, W, H - 60], fill=C_GOLD)
    ftag = _font(FONT_REGULAR, 20)
    scan_txt = 'Scan QR untuk Absensi'
    tw = draw.textlength(scan_txt, font=ftag)
    draw.text(((W - tw) // 2, H - 42), scan_txt, font=ftag, fill=(180, 200, 255))

    buf = io.BytesIO()
    img.save(buf, format='PNG', dpi=(DPI, DPI), optimize=True)
    buf.seek(0)
    return buf.getvalue()


def _draw_logo_placeholder(draw, x, y, size, color):
    """Gambar placeholder 'P' jika tidak ada logo."""
    from PIL import ImageFont
    FONT_BOLD = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
    draw.rounded_rectangle([x, y, x + size, y + size], radius=10,
                            fill=color, outline=(255, 255, 255), width=2)
    f = _font(FONT_BOLD, size - 20)
    draw.text((x + 16, y + 8), 'P', font=f, fill=(255, 255, 255))


# ── Routes ───────────────────────────────────────────────────

@kartu_bp.route('/kartu')
@login_required
def index():
    kelas = request.args.get('kelas', '')
    q     = request.args.get('q', '').strip()
    query = Santri.query
    if kelas:
        query = query.filter_by(kelas=kelas)
    if q:
        query = query.filter(
            Santri.nama.ilike(f'%{q}%') | Santri.nis.ilike(f'%{q}%')
        )
    santri_list = query.order_by(Santri.kelas, Santri.nama).all()
    return render_template('kartu.html',
        santri_list=santri_list, kelas=kelas, q=q,
        kelas_list=KELAS_LIST, total=Santri.query.count())


@kartu_bp.route('/kartu/preview/<int:id>')
@login_required
def preview(id):
    s   = Santri.query.get_or_404(id)
    png = _buat_kartu(s)
    return Response(png, mimetype='image/png',
                    headers={'Cache-Control': 'no-cache'})


@kartu_bp.route('/kartu/unduh/<int:id>')
@login_required
def unduh(id):
    s    = Santri.query.get_or_404(id)
    png  = _buat_kartu(s)
    nama = s.nama.replace(' ', '_')
    return send_file(io.BytesIO(png), mimetype='image/png',
                     as_attachment=True,
                     download_name=f'kartu_{s.nis}_{nama}.png')


@kartu_bp.route('/kartu/unduh-semua')
@login_required
def unduh_semua():
    kelas = request.args.get('kelas', '')
    ids   = request.args.getlist('ids')
    query = Santri.query
    if ids:
        query = query.filter(Santri.id.in_([int(i) for i in ids]))
    elif kelas:
        query = query.filter_by(kelas=kelas)
    santri_list = query.order_by(Santri.kelas, Santri.nama).all()
    if not santri_list:
        return 'Tidak ada data santri.', 404

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for s in santri_list:
            try:
                png    = _buat_kartu(s)
                nama   = s.nama.replace(' ', '_')
                folder = (s.kelas or 'Lainnya').replace(' ', '_')
                zf.writestr(f'{folder}/kartu_{s.nis}_{nama}.png', png)
            except Exception:
                continue

    zip_buf.seek(0)
    label = f'_kelas_{kelas.replace(" ","_")}' if kelas else '_semua'
    return send_file(zip_buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'kartu_santri{label}.zip')
