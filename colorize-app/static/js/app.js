/**
 * 时光上色 - Frontend Logic
 */

let currentFile = null;
let currentTaskId = null;
let resultBase64 = null;

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const processingArea = document.getElementById('processingArea');
const resultArea = document.getElementById('resultArea');
const progressFill = document.getElementById('progressFill');
const beforeImg = document.getElementById('beforeImg');
const afterImg = document.getElementById('afterImg');
const compareHandle = document.getElementById('compareHandle');

// ===== Upload Handlers =====
if (uploadArea) {
    uploadArea.addEventListener('click', () => fileInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        alert('请上传图片文件（JPG、PNG）');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
        alert('图片大小不能超过 10MB');
        return;
    }
    
    currentFile = file;
    uploadFile(file);
}

async function uploadFile(file) {
    // Show processing
    uploadArea.hidden = true;
    processingArea.hidden = false;
    resultArea.hidden = true;
    
    // Simulate progress
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) progress = 90;
        progressFill.style.width = progress + '%';
    }, 200);
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/colorize', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        clearInterval(progressInterval);
        
        if (data.success) {
            progressFill.style.width = '100%';
            currentTaskId = data.task_id;
            resultBase64 = data.result;
            
            // Show result after short delay
            setTimeout(() => {
                showResult();
            }, 500);
        } else {
            throw new Error(data.message || '上色失败');
        }
    } catch (error) {
        clearInterval(progressInterval);
        alert('上传失败: ' + error.message);
        resetUpload();
    }
}

function showResult() {
    processingArea.hidden = true;
    resultArea.hidden = false;
    
    // Set before image (original)
    const reader = new FileReader();
    reader.onload = (e) => {
        beforeImg.style.backgroundImage = `url(${e.target.result})`;
    };
    reader.readAsDataURL(currentFile);
    
    // Set after image (colorized)
    afterImg.style.backgroundImage = `url(${resultBase64})`;
    
    // Init compare slider
    initCompareSlider();
}

function initCompareSlider() {
    const container = document.getElementById('compareContainer');
    if (!container) return;
    
    let isDragging = false;
    
    container.addEventListener('mousedown', startDrag);
    container.addEventListener('touchstart', startDrag);
    document.addEventListener('mousemove', drag);
    document.addEventListener('touchmove', drag);
    document.addEventListener('mouseup', stopDrag);
    document.addEventListener('touchend', stopDrag);
    
    function startDrag(e) {
        isDragging = true;
        e.preventDefault();
    }
    
    function drag(e) {
        if (!isDragging) return;
        
        const rect = container.getBoundingClientRect();
        const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
        const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
        
        afterImg.style.clipPath = `inset(0 ${100 - percentage}% 0 0)`;
        compareHandle.style.left = percentage + '%';
    }
    
    function stopDrag() {
        isDragging = false;
    }
}

function downloadResult() {
    if (!resultBase64) return;
    
    const link = document.createElement('a');
    link.href = resultBase64;
    link.download = 'colorized_' + currentTaskId + '.png';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function shareResult() {
    if (navigator.share) {
        navigator.share({
            title: '时光上色 - 我的照片上色了！',
            text: '看看我的黑白照片被 AI 上色后的效果！',
            url: window.location.href
        });
    } else {
        // Copy link to clipboard
        navigator.clipboard.writeText(window.location.href);
        alert('链接已复制到剪贴板！');
    }
}

function resetUpload() {
    currentFile = null;
    currentTaskId = null;
    resultBase64 = null;
    
    uploadArea.hidden = false;
    processingArea.hidden = true;
    resultArea.hidden = true;
    
    progressFill.style.width = '0%';
    fileInput.value = '';
    
    // Scroll back to upload
    scrollToUpload();
}

function scrollToUpload() {
    document.getElementById('uploadSection').scrollIntoView({ 
        behavior: 'smooth' 
    });
}

// ===== Hero Animation =====
document.addEventListener('DOMContentLoaded', () => {
    // Animate the compare slider in hero
    const heroCompare = document.getElementById('heroCompare');
    if (heroCompare) {
        let position = 50;
        let direction = 1;
        
        setInterval(() => {
            position += direction * 0.5;
            if (position > 70 || position < 30) direction *= -1;
            
            const after = heroCompare.querySelector('.compare-after');
            const slider = heroCompare.querySelector('.compare-slider');
            
            if (after) after.style.clipPath = `inset(0 ${100 - position}% 0 0)`;
            if (slider) slider.style.left = position + '%';
        }, 50);
    }
});
