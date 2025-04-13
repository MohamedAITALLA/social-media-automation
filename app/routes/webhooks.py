# app/routes/webhooks.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.webhook import Webhook
from app.services.webhook_service import WebhookService
from bson.objectid import ObjectId

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/')
def index():
    webhooks = Webhook.get_all()
    return render_template('webhooks.html', webhooks=webhooks)

@webhooks_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        description = request.form.get('description', '').strip()
        
        # Parse headers from form data
        headers = {}
        header_keys = request.form.getlist('header_key[]')
        header_values = request.form.getlist('header_value[]')
        
        for key, value in zip(header_keys, header_values):
            if key.strip():
                headers[key.strip()] = value.strip()
        
        # Validate URL
        if not url:
            flash('Webhook URL is required', 'error')
            return redirect(url_for('webhooks.add'))
        
        # Create webhook
        Webhook.create(url, description, headers)
        flash('Webhook added successfully', 'success')
        return redirect(url_for('webhooks.index'))
    
    return render_template('webhooks_add.html')

@webhooks_bp.route('/<webhook_id>')
def view(webhook_id):
    webhook = Webhook.get_by_id(webhook_id)
    if not webhook:
        flash('Webhook not found', 'error')
        return redirect(url_for('webhooks.index'))
    
    # Get webhook delivery history
    delivery_history = WebhookService.get_delivery_history(webhook_id)
    
    return render_template('webhooks_view.html', webhook=webhook, delivery_history=delivery_history)

@webhooks_bp.route('/<webhook_id>/edit', methods=['GET', 'POST'])
def edit(webhook_id):
    webhook = Webhook.get_by_id(webhook_id)
    if not webhook:
        flash('Webhook not found', 'error')
        return redirect(url_for('webhooks.index'))
    
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        description = request.form.get('description', '').strip()
        active = 'active' in request.form
        
        # Parse headers from form data
        headers = {}
        header_keys = request.form.getlist('header_key[]')
        header_values = request.form.getlist('header_value[]')
        
        for key, value in zip(header_keys, header_values):
            if key.strip():
                headers[key.strip()] = value.strip()
        
        # Validate URL
        if not url:
            flash('Webhook URL is required', 'error')
            return redirect(url_for('webhooks.edit', webhook_id=webhook_id))
        
        # Update webhook
        Webhook.update(webhook_id, url, description, headers, active)
        flash('Webhook updated successfully', 'success')
        return redirect(url_for('webhooks.index'))
    
    return render_template('webhooks_edit.html', webhook=webhook)

@webhooks_bp.route('/<webhook_id>/toggle', methods=['POST'])
def toggle(webhook_id):
    webhook = Webhook.get_by_id(webhook_id)
    if not webhook:
        return jsonify({'success': False, 'error': 'Webhook not found'}), 404
    
    new_status = not webhook.get('active', True)
    Webhook.update(webhook_id, active=new_status)
    
    return jsonify({
        'success': True,
        'active': new_status
    })

@webhooks_bp.route('/<webhook_id>/test', methods=['POST'])
def test(webhook_id):
    # Get optional custom message from form
    test_message = request.form.get('test_message', '')
    
    # Call the correct method
    result = WebhookService.send_test_notification(webhook_id, test_message)
    
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'error')
    
    return redirect(url_for('webhooks.view', webhook_id=webhook_id))

@webhooks_bp.route('/<webhook_id>/delete', methods=['POST'])
def delete(webhook_id):
    webhook = Webhook.get_by_id(webhook_id)
    if not webhook:
        flash('Webhook not found', 'error')
        return redirect(url_for('webhooks.index'))
    
    Webhook.delete(webhook_id)
    flash('Webhook deleted successfully', 'success')
    return redirect(url_for('webhooks.index'))
