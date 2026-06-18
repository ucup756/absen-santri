from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from extensions import db
from models import Acara
from datetime import date

acara_bp = Blueprint('acara', __name__)

@acara_bp.route('/acara')
@login_required
def index():
    q          = request.args.get('q', '').strip()
    query      = Acara.query
    if q:
        query  = query.filter(Acara.nama.ilike(f'%{q}%'))
    acara_list = query.order_by(Acara.dibuat.desc()).all()
    return render_template('acara.html', acara_list=acara_list, q=q, today=date.today())


@acara_bp.route('/acara/tambah', methods=['POST'])
@login_required
def tambah():
    nama            = request.form.get('nama', '').strip()
    deskripsi       = request.form.get('deskripsi', '').strip()
    tanggal         = request.form.get('tanggal')
    jam_mulai       = request.form.get('jam_mulai')
    jam_selesai     = request.form.get('jam_selesai')
    batas_terlambat = request.form.get('batas_terlambat')

    if not all([nama, tanggal, jam_mulai, jam_selesai, batas_terlambat]):
        flash('Semua field wajib diisi!', 'danger')
        return redirect(url_for('acara.index'))

    db.session.add(Acara(
        nama=nama, deskripsi=deskripsi,
        tanggal=date.fromisoformat(tanggal),
        jam_mulai=jam_mulai, jam_selesai=jam_selesai,
        batas_terlambat=batas_terlambat, status='tutup'
    ))
    db.session.commit()
    flash(f'Acara "{nama}" berhasil ditambahkan.', 'success')
    return redirect(url_for('acara.index'))


@acara_bp.route('/acara/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    a = Acara.query.get_or_404(id)
    a.nama            = request.form.get('nama', '').strip()
    a.deskripsi       = request.form.get('deskripsi', '').strip()
    a.tanggal         = date.fromisoformat(request.form.get('tanggal'))
    a.jam_mulai       = request.form.get('jam_mulai')
    a.jam_selesai     = request.form.get('jam_selesai')
    a.batas_terlambat = request.form.get('batas_terlambat')
    db.session.commit()
    flash('Acara berhasil diperbarui.', 'success')
    return redirect(url_for('acara.index'))


@acara_bp.route('/acara/toggle/<int:id>', methods=['POST'])
@login_required
def toggle(id):
    a        = Acara.query.get_or_404(id)
    a.status = 'tutup' if a.status == 'buka' else 'buka'
    db.session.commit()
    label = 'dibuka' if a.status == 'buka' else 'ditutup'
    flash(f'Sesi absensi "{a.nama}" {label}.', 'success')
    return redirect(url_for('acara.index'))


@acara_bp.route('/acara/hapus/<int:id>', methods=['POST'])
@login_required
def hapus(id):
    a = Acara.query.get_or_404(id)
    nama = a.nama
    db.session.delete(a)
    db.session.commit()
    flash(f'Acara "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('acara.index'))
