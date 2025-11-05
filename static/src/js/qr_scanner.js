/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * QR Scanner Widget for Rental Management
 * Uses device camera to scan QR codes on mobile devices
 */

export class RentalQRScanner extends Component {
    setup() {
        // this.rpc = useService("rpc");
        this.notification = useService("notification");
        
        this.state = useState({
            isScanning: false,
            cameraActive: false,
            lastScanned: null,
            scanResult: null,
            videoDevices: [],
            selectedCamera: null,
            scanType: 'verify',
            context: {},
        });
        
        this.videoRef = null;
        this.canvasRef = null;
        this.scanInterval = null;
        
        onMounted(() => {
            this.initializeScanner();
        });
        
        onWillUnmount(() => {
            this.stopScanning();
        });
    }
    
    async initializeScanner() {
        // Load the QR code scanning library (jsQR)
        // This would need to be included in your module assets
        try {
            await this.loadJsQR();
            await this.getCameras();
        } catch (error) {
            console.error("Failed to initialize scanner:", error);
            this.notification.add("Failed to initialize camera", {
                type: "danger",
            });
        }
    }
    
    async loadJsQR() {
        // Load jsQR library if not already loaded
        if (typeof jsQR === 'undefined') {
            return new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = '/rental_management/static/lib/jsQR/jsQR.js';
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            });
        }
    }
    
    async getCameras() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const videoDevices = devices.filter(device => device.kind === 'videoinput');
            
            this.state.videoDevices = videoDevices;
            
            // Prefer back camera on mobile
            const backCamera = videoDevices.find(device => 
                device.label.toLowerCase().includes('back') ||
                device.label.toLowerCase().includes('rear')
            );
            
            this.state.selectedCamera = backCamera ? backCamera.deviceId : 
                (videoDevices.length > 0 ? videoDevices[0].deviceId : null);
                
        } catch (error) {
            console.error("Error getting cameras:", error);
        }
    }
    
    async startScanning() {
        if (this.state.cameraActive) {
            this.stopScanning();
            return;
        }
        
        try {
            const constraints = {
                video: {
                    deviceId: this.state.selectedCamera ? 
                        { exact: this.state.selectedCamera } : undefined,
                    facingMode: this.state.selectedCamera ? undefined : 'environment',
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };
            
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            this.videoRef = document.getElementById('qr-video');
            this.canvasRef = document.getElementById('qr-canvas');
            
            if (this.videoRef) {
                this.videoRef.srcObject = stream;
                this.videoRef.setAttribute('playsinline', true);
                await this.videoRef.play();
                
                this.state.cameraActive = true;
                this.state.isScanning = true;
                
                // Start scanning loop
                this.scanInterval = setInterval(() => {
                    this.scanFrame();
                }, 100); // Scan every 100ms
            }
            
        } catch (error) {
            console.error("Error starting camera:", error);
            this.notification.add("Could not access camera. Please check permissions.", {
                type: "danger",
            });
        }
    }
    
    stopScanning() {
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }
        
        if (this.videoRef && this.videoRef.srcObject) {
            const tracks = this.videoRef.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            this.videoRef.srcObject = null;
        }
        
        this.state.cameraActive = false;
        this.state.isScanning = false;
    }
    
    scanFrame() {
        if (!this.videoRef || !this.canvasRef || !this.videoRef.readyState === this.videoRef.HAVE_ENOUGH_DATA) {
            return;
        }
        
        const canvas = this.canvasRef;
        const video = this.videoRef;
        const ctx = canvas.getContext('2d');
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        // Use jsQR to decode
        if (typeof jsQR !== 'undefined') {
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
            });
            
            if (code && code.data) {
                this.onQRCodeDetected(code.data);
            }
        }
    }
    
    async onQRCodeDetected(data) {
        // Prevent duplicate scans
        if (this.state.lastScanned === data) {
            return;
        }
        
        this.state.lastScanned = data;
        
        // Vibrate if available (mobile feedback)
        if (navigator.vibrate) {
            navigator.vibrate(200);
        }
        
        // Process the scanned code
        await this.processScannedCode(data);
        
        // Clear last scanned after 2 seconds to allow re-scanning
        setTimeout(() => {
            if (this.state.lastScanned === data) {
                this.state.lastScanned = null;
            }
        }, 2000);
    }
    
    async processScannedCode(serialNumber) {
        try {
            const response = await fetch('/rental/scanner/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        serial_number: serialNumber,
                        scan_type: this.state.scanType,
                        context: this.state.context,
                    }
                })
            });

            const data = await response.json();
            const result = data.result; // Odoo wraps result in { result: ... }

            this.state.scanResult = result;
            if (result.status === 'success') {
                this.notification.add(result.message, { type: "success" });
            } else if (result.status === 'warning') {
                this.notification.add(result.message, { type: "warning" });
            } else if (result.status === 'error') {
                this.notification.add(result.message, { type: "danger" });
            } else {
                this.notification.add(result.message, { type: "info" });
            }
        } catch (error) {
            console.error("Error processing scanned code:", error);
            this.notification.add("Failed to process scan", { type: "danger" });
        }
    }
    
    onScanTypeChange(event) {
        this.state.scanType = event.target.value;
    }
    
    onCameraChange(event) {
        this.state.selectedCamera = event.target.value;
        if (this.state.cameraActive) {
            this.stopScanning();
            setTimeout(() => this.startScanning(), 100);
        }
    }
    
    clearResult() {
        this.state.scanResult = null;
        this.state.lastScanned = null;
    }
}

RentalQRScanner.template = "rental_management.QRScannerTemplate";

// Register as a client action
registry.category("actions").add("rental_qr_scanner", RentalQRScanner);
