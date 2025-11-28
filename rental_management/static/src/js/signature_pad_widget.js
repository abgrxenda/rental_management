/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Signature Pad Widget
 * Allows users to draw signatures on screen using mouse or stylus
 */
export class SignaturePadWidget extends Component {
    static template = "rental_management.SignaturePadWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.canvasRef = useRef("signatureCanvas");
        this.state = useState({
            isDrawing: false,
            isEmpty: true,
        });
        
        onMounted(() => {
            this.setupCanvas();
            this.loadExistingSignature();
        });
        
        onWillUnmount(() => {
            this.removeEventListeners();
        });
    }
    
    get isReadonly() {
        return this.props.readonly || false;
    }
    
    get fieldValue() {
        return this.props.record.data[this.props.name];
    }
    
    setupCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        
        this.ctx = canvas.getContext('2d');
        
        // Set canvas size
        const container = canvas.parentElement;
        canvas.width = container.offsetWidth || 600;
        canvas.height = 200;
        
        // Set drawing style
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 2;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        
        // Add event listeners
        if (!this.isReadonly) {
            this.addEventListeners();
        }
    }
    
    addEventListeners() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        
        // Mouse events
        canvas.addEventListener('mousedown', this.startDrawing.bind(this));
        canvas.addEventListener('mousemove', this.draw.bind(this));
        canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
        canvas.addEventListener('mouseleave', this.stopDrawing.bind(this));
        
        // Touch events (for tablets/stylus)
        canvas.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        canvas.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        canvas.addEventListener('touchend', this.stopDrawing.bind(this));
    }
    
    removeEventListeners() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        
        canvas.removeEventListener('mousedown', this.startDrawing);
        canvas.removeEventListener('mousemove', this.draw);
        canvas.removeEventListener('mouseup', this.stopDrawing);
        canvas.removeEventListener('mouseleave', this.stopDrawing);
        canvas.removeEventListener('touchstart', this.handleTouchStart);
        canvas.removeEventListener('touchmove', this.handleTouchMove);
        canvas.removeEventListener('touchend', this.stopDrawing);
    }
    
    startDrawing(e) {
        if (this.isReadonly) return;
        
        this.state.isDrawing = true;
        this.state.isEmpty = false;
        const pos = this.getPosition(e);
        this.ctx.beginPath();
        this.ctx.moveTo(pos.x, pos.y);
    }
    
    draw(e) {
        if (!this.state.isDrawing || this.isReadonly) return;
        
        const pos = this.getPosition(e);
        this.ctx.lineTo(pos.x, pos.y);
        this.ctx.stroke();
    }
    
    stopDrawing() {
        if (!this.state.isDrawing) return;
        
        this.state.isDrawing = false;
        this.ctx.closePath();
        
        // Save signature as base64
        this.saveSignature();
    }
    
    handleTouchStart(e) {
        if (this.isReadonly) return;
        
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.canvasRef.el.dispatchEvent(mouseEvent);
    }
    
    handleTouchMove(e) {
        if (this.isReadonly) return;
        
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.canvasRef.el.dispatchEvent(mouseEvent);
    }
    
    getPosition(e) {
        const canvas = this.canvasRef.el;
        const rect = canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }
    
    saveSignature() {
        if (this.isReadonly) return;
        
        const canvas = this.canvasRef.el;
        const dataURL = canvas.toDataURL('image/png');
        const base64 = dataURL.split(',')[1];
        
        // Update the field value
        this.props.record.update({
            [this.props.name]: base64
        });
    }
    
    clearSignature() {
        if (this.isReadonly) return;
        
        const canvas = this.canvasRef.el;
        if (!canvas || !this.ctx) return;
        
        this.ctx.clearRect(0, 0, canvas.width, canvas.height);
        this.state.isEmpty = true;
        
        // Clear the field value
        this.props.record.update({
            [this.props.name]: false
        });
    }
    
    loadExistingSignature() {
        const value = this.fieldValue;
        if (!value) {
            this.state.isEmpty = true;
            return;
        }
        
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        
        const img = new Image();
        img.onload = () => {
            this.ctx.clearRect(0, 0, canvas.width, canvas.height);
            this.ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            this.state.isEmpty = false;
        };
        img.onerror = () => {
            console.error('Failed to load signature image');
            this.state.isEmpty = true;
        };
        img.src = 'data:image/png;base64,' + value;
    }
}

// Register the widget
registry.category("fields").add("signature_pad", SignaturePadWidget);