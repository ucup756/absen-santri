from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import Santri

santri_bp = Blueprint('santri', __name__)

KELAS_LIST = ['Kelas 1A','Kelas 1B','Kelas 2A','Kelas 2B',
              'Kelas 3A','Kelas 3B','Kelas 4A','Kelas 4B']

@santri_bp.route('/santri')
@login_required
def index():
    q    = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    query = Santri.query
    if q:
        query = query.filter(
            Santri.nama.ilike(f'%{q}%') |
            Santri.nis.ilike(f'%{q}%')  |
            Santri.kelas.ilike(f'%{q}%')
        )
    santri = query.order_by(Santri.dibuat.desc()).paginate(page=page, per_page=10)
    return render_template('santri.html', santri=santri, q=q, kelas_list=KELAS_LIST)


@santri_bp.route('/santri/tambah', methods=['POST'])
@login_required
def tambah():
    nis       = request.form.get('nis', '').strip()
    nama      = request.form.get('nama', '').strip()
    orang_tua = request.form.get('orang_tua', '').strip()
    alamat    = request.form.get('alamat', '').strip()
    kelas     = request.form.get('kelas', '').strip()

    if not nis or not nama:
        flash('NIS dan Nama wajib diisi!', 'danger')
        return redirect(url_for('santri.index'))
    if Santri.query.filter_by(nis=nis).first():
        flash(f'NIS {nis} sudah terdaftar!', 'danger')
        return redirect(url_for('santri.index'))

    db.session.add(Santri(nis=nis, nama=nama, orang_tua=orang_tua, alamat=alamat, kelas=kelas))
    db.session.commit()
    flash(f'Santri "{nama}" berhasil ditambahkan.', 'success')
    return redirect(url_for('santri.index'))


@santri_bp.route('/santri/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    s   = Santri.query.get_or_404(id)
    nis = request.form.get('nis', '').strip()
    if Santri.query.filter(Santri.nis == nis, Santri.id != id).first():
        flash(f'NIS {nis} sudah digunakan santri lain!', 'danger')
        return redirect(url_for('santri.index'))
    s.nis       = nis
    s.nama      = request.form.get('nama', '').strip()
    s.orang_tua = request.form.get('orang_tua', '').strip()
    s.alamat    = request.form.get('alamat', '').strip()
    s.kelas     = request.form.get('kelas', '').strip()
    db.session.commit()
    flash('Data santri berhasil diperbarui.', 'success')
    return redirect(url_for('santri.index'))


@santri_bp.route('/santri/hapus/<int:id>', methods=['POST'])
@login_required
def hapus(id):
    s = Santri.query.get_or_404(id)
    nama = s.nama
    db.session.delete(s)
    db.session.commit()
    flash(f'Santri "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('santri.index'))


@santri_bp.route('/santri/qr/<int:id>')
@login_required
def qr(id):
    s = Santri.query.get_or_404(id)
    return render_template('qr_modal.html', santri=s, qr_b64=s.qr_base64())
