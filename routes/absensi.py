from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from extensions import db
from models import Santri, Acara, Absensi
from datetime import datetime

absensi_bp = Blueprint('absensi', __name__)


@absensi_bp.route('/absensi')
@login_required
def index():
    acara_buka  = Acara.query.filter_by(status='buka').all()
    acara_semua = Acara.query.order_by(Acara.dibuat.desc()).all()
    selected_id = request.args.get('acara_id', type=int)
    today_abs   = []
    if selected_id:
        today_abs = (Absensi.query
                     .filter_by(acara_id=selected_id)
                     .order_by(Absensi.waktu.desc())
                     .limit(30).all())
    return render_template('absensi.html',
        acara_buka=acara_buka, acara_semua=acara_semua,
        selected_id=selected_id, today_abs=today_abs)


@absensi_bp.route('/absensi/scan', methods=['POST'])
@login_required
def scan():
    """Terima NIS dari scan kamera (jsQR) atau input manual → catat absensi."""
    data     = request.get_json(silent=True) or {}
    nis      = (data.get('nis') or '').strip().upper()
    acara_id = data.get('acara_id')
    return _proses_absensi(nis, acara_id)


@absensi_bp.route('/absensi/scan-foto', methods=['POST'])
@login_required
def scan_foto():
    """Terima gambar QR → decode pakai pyzbar/OpenCV → catat absensi."""
    file     = request.files.get('file')
    acara_id = request.form.get('acara_id', type=int)

    if not file:
        return jsonify(ok=False, pesan='Tidak ada file gambar.')

    # Baca gambar
    img_bytes = file.read()
    nis = _decode_qr_from_image(img_bytes)

    if not nis:
        return jsonify(ok=False, pesan='QR Code tidak terdeteksi pada gambar. Coba foto lebih dekat dan pastikan pencahayaan cukup.')

    return _proses_absensi(nis.strip().upper(), acara_id)


def _decode_qr_from_image(img_bytes):
    """Decode QR dari bytes gambar. Coba pyzbar dulu, fallback ke opencv."""
    # ── Coba pyzbar (lebih ringan) ──────────────────
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        results = pyzbar_decode(img)
        if results:
            return results[0].data.decode('utf-8')
    except ImportError:
        pass
    except Exception:
        pass

    # ── Coba opencv ────────────────────────────────
    try:
        import cv2
        import numpy as np
        nparr  = np.frombuffer(img_bytes, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        val, _, _ = detector.detectAndDecode(img_cv)
        if val:
            return val
    except ImportError:
        pass
    except Exception:
        pass

    return None


def _proses_absensi(nis, acara_id):
    """Logic inti pencatatan absensi — dipakai oleh scan & scan_foto."""
    if not nis or not acara_id:
        return jsonify(ok=False, pesan='Data tidak lengkap.')

    acara = Acara.query.get(acara_id)
    if not acara:
        return jsonify(ok=False, pesan='Acara tidak ditemukan.')
    if acara.status != 'buka':
        return jsonify(ok=False, pesan='Sesi absensi sudah ditutup.')

    santri = Santri.query.filter_by(nis=nis).first()
    if not santri:
        return jsonify(ok=False, pesan=f'NIS "{nis}" tidak terdaftar di sistem.')

    sudah = Absensi.query.filter_by(santri_id=santri.id, acara_id=acara.id).first()
    if sudah:
        return jsonify(ok=False,
            pesan=f'{santri.nama} sudah absen pada {sudah.waktu.strftime("%H:%M")}.')

    # Tentukan tepat waktu / terlambat
    now    = datetime.now()
    bh, bm = map(int, acara.batas_terlambat.split(':'))
    from datetime import date as _date
    batas  = datetime.combine(acara.tanggal, datetime.min.time()).replace(hour=bh, minute=bm)
    status = 'terlambat' if now > batas else 'tepat_waktu'

    db.session.add(Absensi(santri_id=santri.id, acara_id=acara.id, waktu=now, status=status))
    db.session.commit()

    return jsonify(
        ok=True, status=status,
        santri=dict(nama=santri.nama, nis=santri.nis, kelas=santri.kelas or '-',
                    alamat=santri.alamat or '-', orang_tua=santri.orang_tua or '-'),
        acara=dict(nama=acara.nama),
        waktu=now.strftime('%d %b %Y, %H:%M:%S')
    )
