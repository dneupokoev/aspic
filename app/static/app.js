// app/static/app.js
// Состояния приложения
const State = {
    UPLOAD: 'upload',
    PREVIEW: 'preview',
    RESULT: 'result'
};

// Текущее состояние
let currentState = State.UPLOAD;
let currentPreviewId = null;
let currentFileData = null;
let isTextEditable = false;
let originalTextContent = null;
let webhookUrl = '';
let deletePassword = '';

// DOM элементы
const elements = {
    stateUpload: document.getElementById('state-upload'),
    statePreview: document.getElementById('state-preview'),
    stateResult: document.getElementById('state-result'),
    fileInput: document.getElementById('fileInput'),
    dropZone: document.getElementById('dropZone'),
    selectFileBtn: document.getElementById('selectFileBtn'),
    pasteTrigger: document.getElementById('pasteTrigger'),
    previewContainer: document.getElementById('previewContainer'),
    previewFilename: document.getElementById('previewFilename'),
    previewFilesize: document.getElementById('previewFilesize'),
    previewType: document.getElementById('previewType'),
    previewIcon: document.getElementById('previewIcon'),
    confirmBtn: document.getElementById('confirmBtn'),
    cancelBtn: document.getElementById('cancelBtn'),
    loadingIndicator: document.getElementById('loadingIndicator'),
    resultLink: document.getElementById('resultLink'),
    viewFileLink: document.getElementById('viewFileLink'),
    copyBtn: document.getElementById('copyBtn'),
    newUploadBtn: document.getElementById('newUploadBtn'),
    errorMessage: document.getElementById('errorMessage')
};

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================

function hideErrorMessage() {
    const clientError = document.getElementById('clientErrorMessage');
    if (clientError) {
        clientError.style.display = 'none';
    }

    const serverError = document.getElementById('serverErrorMessage');
    if (serverError) {
        serverError.style.display = 'none';
    }

    if (elements.errorMessage) {
        elements.errorMessage.style.display = 'none';
    }
}

function setState(state) {
    currentState = state;
    elements.stateUpload.classList.remove('visible');
    elements.statePreview.classList.remove('visible');
    elements.stateResult.classList.remove('visible');
    elements.stateUpload.classList.add('hidden');
    elements.statePreview.classList.add('hidden');
    elements.stateResult.classList.add('hidden');

    const stateMap = {
        [State.UPLOAD]: elements.stateUpload,
        [State.PREVIEW]: elements.statePreview,
        [State.RESULT]: elements.stateResult
    };

    const targetElement = stateMap[state];
    targetElement.classList.remove('hidden');
    targetElement.classList.add('visible');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Б';
    const units = ['Б', 'КБ', 'МБ', 'ГБ'];
    const k = 1024;
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
}

function getFileTypeName(mimeType) {
    if (mimeType.startsWith('image/')) return 'Изображение';
    if (mimeType.startsWith('video/')) return 'Видео';
    if (mimeType.startsWith('audio/')) return 'Аудио';
    if (mimeType === 'application/pdf') return 'PDF документ';
    if (mimeType.startsWith('text/')) return 'Текстовый документ';
    if (mimeType.includes('document') || mimeType.includes('word')) return 'Word документ';
    if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) return 'Excel таблица';
    if (mimeType.includes('presentation') || mimeType.includes('powerpoint')) return 'Презентация';
    if (mimeType.includes('zip') || mimeType.includes('rar')) return 'Архив';
    return 'Файл';
}

function setLoading(show) {
    if (show) {
        elements.loadingIndicator.classList.remove('hidden');
    } else {
        elements.loadingIndicator.classList.add('hidden');
    }
}

function resetToUpload() {
    setState(State.UPLOAD);
    elements.fileInput.value = '';
    currentPreviewId = null;
    currentFileData = null;
    isTextEditable = false;
    originalTextContent = null;
    webhookUrl = '';
    deletePassword = '';
    elements.previewContainer.innerHTML = '<div class="preview-placeholder">Выберите файл для предпросмотра</div>';

    // Скрываем поля при возврате на главную
    const webhookField = document.getElementById('webhookField');
    const passwordField = document.getElementById('passwordField');
    const expireField = document.getElementById('expireField');
    if (webhookField) webhookField.style.display = 'none';
    if (passwordField) passwordField.style.display = 'none';
    if (expireField) expireField.style.display = 'none';

    // Очищаем значения
    if (document.getElementById('webhookUrl')) document.getElementById('webhookUrl').value = '';
    if (document.getElementById('deletePassword')) document.getElementById('deletePassword').value = '';
    if (document.getElementById('expireDate')) document.getElementById('expireDate').value = '';
    if (document.getElementById('ttlHours')) document.getElementById('ttlHours').value = '';

    // Скрываем все информационные попапы
    hideAllInfo();
}

// ============================================
// ФУНКЦИИ КОПИРОВАНИЯ
// ============================================

function copyToClipboard(text, button, type = 'page') {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showCopyFeedback(button, type);
        }).catch(() => {
            fallbackCopy(text, button, type);
        });
    } else {
        fallbackCopy(text, button, type);
    }
}

function fallbackCopy(text, button, type) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, 99999);

    try {
        const success = document.execCommand('copy');
        if (success) {
            showCopyFeedback(button, type);
        } else {
            showCopyFeedback(button, type, true);
        }
    } catch (err) {
        showCopyFeedback(button, type, true);
    }

    document.body.removeChild(textarea);
}

function showCopyFeedback(button, type, isError = false) {
    const originalText = button.textContent;
    const originalHtml = button.innerHTML;

    if (isError) {
        button.textContent = '❌';
    } else {
        if (type === 'page') {
            button.textContent = '✅ Скопировано!';
        } else {
            button.innerHTML = '✅';
        }
    }

    button.disabled = true;

    setTimeout(() => {
        if (type === 'file') {
            button.innerHTML = originalHtml;
        } else {
            button.textContent = originalText;
        }
        button.disabled = false;
    }, 2000);
}

function copyLinkToClipboard() {
    const linkInput = elements.resultLink;
    if (!linkInput) return;

    const textToCopy = linkInput.value;

    if (!textToCopy || textToCopy.includes('undefined') || textToCopy === '') {
        alert('Ошибка: ссылка не сформирована');
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            showCopyFeedback(elements.copyBtn, 'page');
        }).catch(() => {
            fallbackCopy(textToCopy, elements.copyBtn, 'page');
        });
    } else {
        fallbackCopy(textToCopy, elements.copyBtn, 'page');
    }
}

// ============================================
// ФУНКЦИИ ДЛЯ РАБОТЫ С БУФЕРОМ ОБМЕНА
// ============================================

function dataURLtoFile(dataurl, filename) {
    let arr = dataurl.split(','),
        mime = arr[0].match(/:(.*?);/)[1],
        bstr = atob(arr[arr.length - 1]),
        n = bstr.length,
        u8arr = new Uint8Array(n);
    while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new File([u8arr], filename, { type: mime });
}

// Глобальный обработчик вставки
async function handlePaste(event) {
    if (currentState !== State.UPLOAD) {
        return;
    }

    event.preventDefault();

    const clipboardItems = event.clipboardData.items;
    let fileFromClipboard = null;
    let textFromClipboard = null;

    for (let i = 0; i < clipboardItems.length; i++) {
        const item = clipboardItems[i];

        if (item.kind === 'file') {
            const blob = item.getAsFile();
            if (blob && blob.type.startsWith('image/')) {
                fileFromClipboard = blob;
                break;
            }
        }

        if (item.kind === 'string' && item.type === 'text/plain') {
            textFromClipboard = await new Promise((resolve) => {
                item.getAsString(resolve);
            });
        }
    }

    if (fileFromClipboard) {
        const fileName = `clipboard_image_${new Date().toISOString().slice(0,19).replace(/[-:]/g, '')}.png`;
        const newFile = new File([fileFromClipboard], fileName, { type: fileFromClipboard.type });
        uploadForPreview(newFile);
        return;
    }

    if (textFromClipboard && textFromClipboard.trim()) {
        const fileName = `clipboard_text_${new Date().toISOString().slice(0,19).replace(/[-:]/g, '')}.txt`;
        const textBlob = new Blob([textFromClipboard], { type: 'text/plain' });
        const textFile = new File([textBlob], fileName, { type: 'text/plain' });
        uploadForPreview(textFile, textFromClipboard);
        return;
    }

    alert('Буфер обмена не содержит изображения или текста для вставки.');
}

async function activatePaste() {
    if (currentState !== State.UPLOAD) {
        return;
    }

    try {
        const clipboardItems = await navigator.clipboard.read();

        if (!clipboardItems || clipboardItems.length === 0) {
            alert('Не удалось вставить из буфера обмена.');
            return;
        }

        const item = clipboardItems[0];
        let fileFromClipboard = null;
        let textFromClipboard = null;

        for (const type of item.types) {
            if (type.startsWith('image/')) {
                const blob = await item.getType(type);
                if (blob && blob.type.startsWith('image/')) {
                    fileFromClipboard = blob;
                    break;
                }
            }
        }

        if (!fileFromClipboard && item.types.includes('text/plain')) {
            const blob = await item.getType('text/plain');
            textFromClipboard = await blob.text();
        }

        if (fileFromClipboard) {
            const fileName = `clipboard_image_${new Date().toISOString().slice(0,19).replace(/[-:]/g, '')}.png`;
            const newFile = new File([fileFromClipboard], fileName, { type: fileFromClipboard.type });
            uploadForPreview(newFile);
            return;
        }

        if (textFromClipboard && textFromClipboard.trim()) {
            const fileName = `clipboard_text_${new Date().toISOString().slice(0,19).replace(/[-:]/g, '')}.txt`;
            const textBlob = new Blob([textFromClipboard], { type: 'text/plain' });
            const textFile = new File([textBlob], fileName, { type: 'text/plain' });
            uploadForPreview(textFile, textFromClipboard);
            return;
        }

        alert('Не удалось вставить из буфера обмена.');

    } catch (err) {
        console.error('Ошибка чтения буфера:', err);
        alert('Не удалось вставить из буфера обмена.');
    }
}

// ============================================
// ФУНКЦИИ ДЛЯ ОБРАБОТКИ ОШИБОК
// ============================================

function showError(message, isRateLimit = false) {
    const errorDiv = document.getElementById('clientErrorMessage');
    if (!errorDiv) return;

    const errorText = document.getElementById('clientErrorText');
    const errorIcon = document.getElementById('clientErrorIcon');

    let cleanMessage = message.replace(/[✅❌🔒⏳⚠️]/g, '').trim();

    if (isRateLimit) {
        errorIcon.textContent = '⏳';
    } else if (message.includes('❌')) {
        errorIcon.textContent = '❌';
    } else if (message.includes('🔒')) {
        errorIcon.textContent = '🔒';
    } else {
        errorIcon.textContent = '⚠️';
    }

    errorText.textContent = cleanMessage;
    errorDiv.style.display = 'flex';
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });

    setTimeout(() => {
        if (errorDiv.style.display === 'flex') {
            errorDiv.style.display = 'none';
        }
    }, 10000);
}

// ============================================
// ФУНКЦИИ ВАЛИДАЦИИ
// ============================================

function isValidUrl(string) {
    if (!string || string.trim() === '') return true;
    try {
        const url = new URL(string);
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
        return false;
    }
}

function validateWebhookUrl() {
    const webhookInput = document.getElementById('webhookUrl');
    const confirmBtn = document.getElementById('confirmBtn');
    if (!webhookInput || !confirmBtn) return;

    const url = webhookInput.value.trim();
    const isValid = isValidUrl(url);

    if (url.length > 0 && !isValid) {
        webhookInput.classList.add('error-field');
    } else {
        webhookInput.classList.remove('error-field');
    }
    validateForm();
}

function validatePassword() {
    const passwordInput = document.getElementById('deletePassword');
    if (!passwordInput) return true;

    const password = passwordInput.value.trim();

    if (password.length > 0 && (password.length < 4 || password.length > 16)) {
        passwordInput.classList.add('error-field');
        return false;
    } else {
        passwordInput.classList.remove('error-field');
        return true;
    }
}

function validateForm() {
    const webhookInput = document.getElementById('webhookUrl');
    const passwordInput = document.getElementById('deletePassword');
    const confirmBtn = document.getElementById('confirmBtn');
    if (!confirmBtn) return;

    let isValid = true;

    if (webhookInput) {
        const webhookUrl = webhookInput.value.trim();
        if (webhookUrl.length > 0 && !isValidUrl(webhookUrl)) {
            isValid = false;
        }
    }

    if (passwordInput) {
        const password = passwordInput.value.trim();
        if (password.length > 0 && (password.length < 4 || password.length > 16)) {
            isValid = false;
        }
    }

    confirmBtn.disabled = !isValid;
    confirmBtn.title = isValid ? '' : 'Исправьте ошибки в форме';
}

// ============================================
// ОСНОВНЫЕ ФУНКЦИИ
// ============================================

async function uploadForPreview(file, textContent = null) {
    if (!file) return;
    hideErrorMessage();

    const formData = new FormData();
    formData.append('file', file);

    elements.previewContainer.innerHTML = '<div class="preview-placeholder">⏳ Загрузка предпросмотра...</div>';

    try {
        const response = await fetch('/api/preview', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        if (!response.ok) {
            let errorMsg = 'Ошибка загрузки';
            let isRateLimit = false;

            if (response.status === 429) {
                errorMsg = '⏳ Слишком много попыток загрузки. Подождите 1 минуту.';
                isRateLimit = true;
            } else {
                try {
                    const errorData = await response.json();
                    errorMsg = '❌ ' + (errorData.detail || 'Ошибка при загрузке файла');
                } catch (e) {
                    errorMsg = '❌ Ошибка при загрузке файла';
                }
            }

            showError(errorMsg, isRateLimit);
            setState(State.UPLOAD);
            elements.previewContainer.innerHTML = '<div class="preview-placeholder">Выберите файл для предпросмотра</div>';
            return;
        }

        const data = await response.json();

        currentPreviewId = data.preview_id;
        currentFileData = data;

        setState(State.PREVIEW);

        elements.previewFilename.textContent = data.filename;
        elements.previewFilesize.textContent = data.size_formatted || formatFileSize(data.size);
        elements.previewType.textContent = getFileTypeName(data.mime_type);
        elements.previewIcon.textContent = data.icon || '📄';

        // ========== ПОКАЗЫВАЕМ ПОЛЯ ==========
        const webhookField = document.getElementById('webhookField');
        const passwordField = document.getElementById('passwordField');
        const expireField = document.getElementById('expireField');

        if (webhookField) {
            webhookField.style.display = 'block';
            webhookField.style.visibility = 'visible';
        }
        if (passwordField) {
            passwordField.style.display = 'block';
            passwordField.style.visibility = 'visible';
        }
        if (expireField) {
            expireField.style.display = 'block';
            expireField.style.visibility = 'visible';
        }

        // ========== УСТАНАВЛИВАЕМ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ ==========
        const expireDateInput = document.getElementById('expireDate');
        const ttlHoursInput = document.getElementById('ttlHours');

        if (expireDateInput && !expireDateInput.value) {
            const defaultValue = expireDateInput.getAttribute('value');
            if (defaultValue) {
                expireDateInput.value = defaultValue;
                console.log('Expire date set to:', defaultValue);
            }
        }

        if (ttlHoursInput && !ttlHoursInput.value) {
            const defaultValue = ttlHoursInput.getAttribute('value');
            if (defaultValue && defaultValue !== '0') {
                ttlHoursInput.value = defaultValue;
                console.log('TTL hours set to:', defaultValue);
            }
        }
        // ========================================================

        const webhookInput = document.getElementById('webhookUrl');
        const passwordInput = document.getElementById('deletePassword');

        if (webhookInput) {
            webhookInput.addEventListener('input', validateWebhookUrl);
            webhookInput.addEventListener('blur', validateWebhookUrl);
        }
        if (passwordInput) {
            passwordInput.addEventListener('input', validatePassword);
            passwordInput.addEventListener('blur', validatePassword);
        }

        if (textContent !== null && data.mime_type.startsWith('text/')) {
            isTextEditable = true;
            originalTextContent = textContent;
            elements.previewContainer.innerHTML = `
                <textarea class="text-editor-area" placeholder="Редактируйте текст..." spellcheck="false">${escapeHtml(textContent)}</textarea>
            `;
        } else {
            isTextEditable = false;
            originalTextContent = null;
            let previewHtml = '';

            if (data.mime_type.startsWith('image/')) {
                previewHtml = `<img src="${data.preview_url}" alt="preview" class="preview-image">`;
            } else if (data.mime_type === 'application/pdf') {
                previewHtml = `<iframe src="${data.preview_url}" class="preview-iframe"></iframe>`;
            } else if (data.mime_type.startsWith('video/')) {
                previewHtml = `<video controls class="preview-video"><source src="${data.preview_url}" type="${data.mime_type}"></video>`;
            } else if (data.mime_type.startsWith('audio/')) {
                previewHtml = `<audio controls class="preview-audio"><source src="${data.preview_url}" type="${data.mime_type}"></audio>`;
            } else if (data.mime_type.startsWith('text/')) {
                previewHtml = `<iframe src="${data.preview_url}" class="preview-iframe"></iframe>`;
            } else {
                previewHtml = `<div class="preview-unsupported"><p>Предпросмотр недоступен для этого типа файлов</p><p class="file-detail">Тип: ${data.mime_type}</p></div>`;
            }

            elements.previewContainer.innerHTML = previewHtml;
        }

        validateForm();

    } catch (error) {
        console.error('Preview error:', error);
        showError('❌ Ошибка при загрузке файла: ' + error.message);
        setState(State.UPLOAD);
        elements.previewContainer.innerHTML = '<div class="preview-placeholder">Выберите файл для предпросмотра</div>';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    }).replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, function(c) {
        return c;
    });
}

async function confirmUpload() {
    if (!currentPreviewId || !currentFileData) {
        alert('Ошибка: нет данных о файле');
        resetToUpload();
        return;
    }

    // ========== ОБЪЯВЛЯЕМ ПЕРЕМЕННЫЕ В НАЧАЛЕ ==========
    let expireDateValue = '';
    let ttlHoursValue = 0;

    // Используем принудительные значения, если они установлены
    if (window.__forcedExpireDate) {
        expireDateValue = window.__forcedExpireDate;
        console.log('Using forced expireDate:', expireDateValue);
    }
    if (window.__forcedTtlHours) {
        ttlHoursValue = window.__forcedTtlHours;
        console.log('Using forced ttlHours:', ttlHoursValue);
    }

    // ========== ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ ==========
    console.log('=== CONFIRM UPLOAD DEBUG ===');

    const expireDateInput = document.getElementById('expireDate');
    const ttlHoursInput = document.getElementById('ttlHours');
    const hiddenExpireDate = document.getElementById('hiddenExpireDate');
    const hiddenTtlHours = document.getElementById('hiddenTtlHours');

    console.log('expireDateInput.value:', expireDateInput?.value);
    console.log('hiddenExpireDate.value:', hiddenExpireDate?.value);
    console.log('ttlHoursInput.value:', ttlHoursInput?.value);
    console.log('hiddenTtlHours.value:', hiddenTtlHours?.value);

    // Берем значение из видимого поля expireDate (если еще не установлено принудительно)
    if (!expireDateValue) {
        if (expireDateInput && expireDateInput.value) {
            expireDateValue = expireDateInput.value;
            console.log('Using expireDateInput.value:', expireDateValue);
        } else if (hiddenExpireDate && hiddenExpireDate.value) {
            expireDateValue = hiddenExpireDate.value;
            console.log('Using hiddenExpireDate.value:', expireDateValue);
        } else {
            // Если ничего нет, устанавливаем дату через 1 год
            const defaultDate = new Date();
            defaultDate.setFullYear(defaultDate.getFullYear() + 1);
            expireDateValue = defaultDate.toISOString().split('T')[0];
            console.log('Using fallback date:', expireDateValue);
        }
    }

    // Берем значение из видимого поля ttlHours (если еще не установлено принудительно)
    if (!ttlHoursValue) {
        if (ttlHoursInput && ttlHoursInput.value && ttlHoursInput.value !== '0') {
            ttlHoursValue = parseInt(ttlHoursInput.value);
            console.log('Using ttlHoursInput.value:', ttlHoursValue);
        } else if (hiddenTtlHours && hiddenTtlHours.value && hiddenTtlHours.value !== '0') {
            ttlHoursValue = parseInt(hiddenTtlHours.value);
            console.log('Using hiddenTtlHours.value:', ttlHoursValue);
        } else {
            ttlHoursValue = 8760; // 1 год
            console.log('Using fallback TTL:', ttlHoursValue);
        }
    }

    console.log('FINAL expireDateValue:', expireDateValue);
    console.log('FINAL ttlHoursValue:', ttlHoursValue);
    console.log('=== END DEBUG ===');

    const webhookInput = document.getElementById('webhookUrl');
    const passwordInput = document.getElementById('deletePassword');

    const webhookUrlValue = webhookInput?.value.trim() || '';
    const deletePasswordValue = passwordInput?.value.trim() || '';

    if (webhookUrlValue && !isValidUrl(webhookUrlValue)) {
        showError('❌ Введите корректный URL (начинается с http:// или https://)');
        if (webhookInput) webhookInput.classList.add('error-field');
        return;
    }

    if (deletePasswordValue && (deletePasswordValue.length < 4 || deletePasswordValue.length > 16)) {
        showError('❌ Пароль должен быть от 4 до 16 символов');
        if (passwordInput) passwordInput.classList.add('error-field');
        return;
    }

    setLoading(true);

    try {
        const requestBody = {
            preview_id: currentPreviewId,
            filename: currentFileData.filename,
            mime_type: currentFileData.mime_type,
            size: currentFileData.size,
            webhook_url: webhookUrlValue,
            delete_password: deletePasswordValue,
            expire_date: expireDateValue,
            ttl_hours: ttlHoursValue
        };

        console.log('📤 REQUEST BODY:', requestBody);

        if (isTextEditable && originalTextContent !== null) {
            const textarea = elements.previewContainer.querySelector('.text-editor-area');
            if (textarea) {
                requestBody.text_content = textarea.value;
            }
        }

        const response = await fetch('/api/confirm-upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            let errorMsg = 'Ошибка сохранения';
            let isRateLimit = false;

            if (response.status === 429) {
                errorMsg = '⏳ Слишком много попыток загрузки. Подождите 1 минуту.';
                isRateLimit = true;
            } else {
                try {
                    const errorData = await response.json();
                    errorMsg = '❌ ' + (errorData.detail || 'Ошибка при сохранении');
                } catch (e) {
                    errorMsg = '❌ Ошибка при сохранении файла';
                }
            }
            throw { message: errorMsg, isRateLimit };
        }

        const data = await response.json();

        const baseUrl = window.location.origin;
        const token = data.token;
        const filePath = `/view/${token}`;
        const fullUrl = baseUrl + filePath;

        elements.resultLink.value = fullUrl;

        const hasWebhook = data.has_webhook || false;

        if (hasWebhook) {
            elements.viewFileLink.style.display = 'none';
            showWebhookParamsField(fullUrl, filePath, token);
        } else {
            elements.viewFileLink.style.display = 'inline-flex';
            elements.viewFileLink.href = filePath;
            hideWebhookParamsField();
        }

        setState(State.RESULT);
        hideErrorMessage();

    } catch (error) {
        console.error('Confirm error:', error);
        showError(error.message || '❌ Ошибка при создании ссылки', error.isRateLimit);
    } finally {
        setLoading(false);
    }
}

// ============================================
// ФУНКЦИИ ДЛЯ РАБОТЫ С ПАРАМЕТРАМИ ВЕБХУКА
// ============================================

function showWebhookParamsField(fullUrl, basePath, token) {
    let paramsField = document.getElementById('webhookParamsField');

    if (!paramsField) {
        const resultCard = document.querySelector('.result-card');
        const resultActions = document.querySelector('.result-actions');

        paramsField = document.createElement('div');
        paramsField.id = 'webhookParamsField';
        paramsField.className = 'webhook-params-field';
        paramsField.innerHTML = `
            <div class="webhook-params-header">
                <span class="label-icon">🔗</span>
                <span class="field-label">Параметры доступа</span>
                <button type="button" class="info-btn" onclick="showWebhookParamsInfo()" title="Что это?">i</button>
            </div>
            <p class="webhook-params-hint">Для доступа к файлу требуются параметры. Введите их в формате key=value, разделяя &</p>
            <div class="webhook-params-example">
                Пример: <code>system_id=123&secret_key=456&lang=ru</code>
            </div>
            <div class="webhook-params-input-group">
                <input type="text" id="webhookParams" class="webhook-params-input" placeholder="system_id=123&secret_key=456" value="" oninput="validateWebhookParams()">
                <button class="btn btn-primary" id="applyWebhookParamsBtn" onclick="applyWebhookParams('${token}')" disabled>
                    <span class="btn-icon">🔓</span>
                    <span class="btn-text">Открыть с параметрами</span>
                </button>
            </div>
            <div id="webhookParamsInfo" class="info-popup hidden">
                <div class="info-content">
                    <strong>🔗 Параметры доступа</strong>
                    <p>Эти параметры будут переданы в вебхук для проверки доступа к файлу. Формат: key1=value1&key2=value2</p>
                    <p>Пример: <code>system_id=123&secret_key=456</code></p>
                    <span class="info-close" onclick="hideWebhookParamsInfo()">✕</span>
                </div>
            </div>
        `;

        if (resultActions) {
            resultCard.insertBefore(paramsField, resultActions);
        } else {
            resultCard.appendChild(paramsField);
        }

        const input = document.getElementById('webhookParams');
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !document.getElementById('applyWebhookParamsBtn').disabled) {
                    applyWebhookParams(token);
                }
            });
        }
    } else {
        const applyBtn = document.getElementById('applyWebhookParamsBtn');
        if (applyBtn) {
            applyBtn.setAttribute('onclick', `applyWebhookParams('${token}')`);
        }
    }

    paramsField.style.display = 'block';
    const input = document.getElementById('webhookParams');
    if (input) {
        input.value = '';
        validateWebhookParams();
    }
}

function hideWebhookParamsField() {
    const paramsField = document.getElementById('webhookParamsField');
    if (paramsField) {
        paramsField.style.display = 'none';
    }
}

function showWebhookParamsInfo() {
    hideAllInfo();
    const info = document.getElementById('webhookParamsInfo');
    if (info) {
        info.classList.remove('hidden');
        setTimeout(() => {
            document.addEventListener('click', function closeInfo(e) {
                if (!info.contains(e.target) && !e.target.classList.contains('info-btn')) {
                    info.classList.add('hidden');
                    document.removeEventListener('click', closeInfo);
                }
            });
        }, 100);
    }
}

function hideWebhookParamsInfo() {
    const info = document.getElementById('webhookParamsInfo');
    if (info) {
        info.classList.add('hidden');
    }
}

function validateWebhookParams() {
    const paramsInput = document.getElementById('webhookParams');
    const applyBtn = document.getElementById('applyWebhookParamsBtn');
    if (!paramsInput || !applyBtn) return;

    const params = paramsInput.value.trim();
    const isValid = params.length > 0 && params.includes('=');
    applyBtn.disabled = !isValid;

    if (params.length > 0 && !params.includes('=')) {
        paramsInput.classList.add('error-field');
    } else {
        paramsInput.classList.remove('error-field');
    }
}

function applyWebhookParams(token) {
    const paramsInput = document.getElementById('webhookParams');
    if (!paramsInput || !token) return;

    const params = paramsInput.value.trim();
    if (!params || !params.includes('=')) {
        showError('❌ Введите корректные параметры в формате key=value');
        return;
    }

    let fullPath = `/view/${token}`;
    if (params) {
        fullPath = params.startsWith('?') ? `/view/${token}${params}` : `/view/${token}?${params}`;
    }
    window.open(fullPath, '_blank');
}

// ============================================
// ФУНКЦИИ ДЛЯ КНОПОК ИНФОРМАЦИИ
// ============================================

function showInfo(type) {
    hideAllInfo();
    const info = document.getElementById(type + 'Info');
    if (info) {
        info.classList.remove('hidden');
        setTimeout(() => {
            document.addEventListener('click', function closeInfo(e) {
                if (!info.contains(e.target) && !e.target.classList.contains('info-btn')) {
                    info.classList.add('hidden');
                    document.removeEventListener('click', closeInfo);
                }
            });
        }, 100);
    }
}

function hideInfo(type) {
    const info = document.getElementById(type + 'Info');
    if (info) {
        info.classList.add('hidden');
    }
}

function hideAllInfo() {
    const infos = document.querySelectorAll('.info-popup');
    infos.forEach(info => info.classList.add('hidden'));
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideAllInfo();
    }
});

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ
// ============================================

if (elements.selectFileBtn) {
    elements.selectFileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.fileInput.click();
    });
}

elements.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) uploadForPreview(file);
    hideErrorMessage();
});

elements.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.add('dragover');
});

elements.dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.remove('dragover');
});

elements.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    elements.dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadForPreview(file);
    hideErrorMessage();
});

elements.dropZone.addEventListener('click', (e) => {
    elements.fileInput.click();
    hideErrorMessage();
});

document.addEventListener('paste', handlePaste);

if (elements.pasteTrigger) {
    elements.pasteTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        activatePaste();
    });
}

elements.confirmBtn.addEventListener('click', () => {
    confirmUpload();
    hideErrorMessage();
});

elements.cancelBtn.addEventListener('click', () => {
    resetToUpload();
    hideErrorMessage();
});

elements.newUploadBtn.addEventListener('click', () => {
    resetToUpload();
    hideErrorMessage();
});

if (elements.copyBtn) {
    elements.copyBtn.addEventListener('click', copyLinkToClipboard);
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================

resetToUpload();

window.addEventListener('beforeunload', (e) => {
    if (currentState === State.PREVIEW && currentPreviewId) {
        e.preventDefault();
        e.returnValue = '';
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const authorInputs = document.querySelectorAll('input[name="author"]');
    const savedAuthor = localStorage.getItem('aspic_author');
    if (savedAuthor) {
        authorInputs.forEach(input => input.value = savedAuthor);
    }
    authorInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.value && this.value.trim()) {
                localStorage.setItem('aspic_author', this.value.trim());
            }
        });
    });
});