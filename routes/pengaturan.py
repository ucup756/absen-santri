from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import Pengaturan
import base64

pengaturan_bp = Blueprint('pengaturan', __name__)

def _detect_image_type(header: bytes):
    """Deteksi tipe gambar dari magic bytes, tanpa imghdr."""
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if header[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'webp'
    return None

@pengaturan_bp.route('/pengaturan', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        nama      = request.form.get('nama_pesantren', '').strip()
        tagline   = request.form.get('tagline', '').strip()
        tahun     = request.form.get('tahun', '').strip()
        hapus_lg  = request.form.get('hapus_logo')
        logo_file = request.files.get('logo')

        if not nama:
            flash('Nama pesantren tidak boleh kosong!', 'danger')
            return redirect(url_for('pengaturan.index'))

        Pengaturan.set('nama_pesantren', nama)
        Pengaturan.set('tagline', tagline)
        Pengaturan.set('tahun', tahun)

        if hapus_lg:
            Pengaturan.set('logo_base64', '')
        elif logo_file and logo_file.filename:
            content = logo_file.read(512 * 1024)   # maks 512 KB
            tipe = _detect_image_type(content[:12])
            if not tipe:
                flash('Format gambar tidak didukung. Gunakan PNG/JPG/GIF/WEBP.', 'danger')
                return redirect(url_for('pengaturan.index'))
            b64 = base64.b64encode(content).decode()
            Pengaturan.set('logo_base64', f'data:image/{tipe};base64,{b64}')

        flash('Pengaturan berhasil disimpan!', 'success')
        return redirect(url_for('pengaturan.index'))

    data = {
        'nama_pesantren' : Pengaturan.get('nama_pesantren', 'Pesantren Digital'),
        'tagline'        : Pengaturan.get('tagline', 'Sistem Absensi Santri'),
        'tahun'          : Pengaturan.get('tahun', ''),
        'logo_base64'    : Pengaturan.get('logo_base64', ''),
    }
    return render_template('pengaturan.html', **data)
