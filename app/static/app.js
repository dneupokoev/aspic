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
    if (webhookField) webhookField.style.display = 'none';
    if (passwordField) passwordField.style.display = 'none';

    // Очищаем значения
    if (document.getElementById('webhookUrl')) document.getElementById('webhookUrl').value = '';
    if (document.getElementById('deletePassword')) document.getElementById('deletePassword').value = '';

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
    // Разрешаем вставку ТОЛЬКО на главной странице (в состоянии UPLOAD)
    if (currentState !== State.UPLOAD) {
        // На других страницах не блокируем стандартное поведение
        return;
    }

    // Предотвращаем стандартное поведение только на главной странице
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

// Функция для активации вставки по клику на кнопку
async function activatePaste() {
    // Проверяем, что мы на главной странице
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

        // Проверяем, есть ли изображение в буфере
        for (const type of item.types) {
            if (type.startsWith('image/')) {
                const blob = await item.getType(type);
                if (blob && blob.type.startsWith('image/')) {
                    fileFromClipboard = blob;
                    break;
                }
            }
        }

        // Если нет изображения, проверяем текст
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
    // Используем новый элемент для клиентских ошибок
    const errorDiv = document.getElementById('clientErrorMessage');
    if (!errorDiv) return;

    const errorText = document.getElementById('clientErrorText');
    const errorIcon = document.getElementById('clientErrorIcon');

    // Очищаем сообщение от эмодзи для отображения
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

    // Прокрутка к ошибке
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Автоматически скрываем через 10 секунд
    setTimeout(() => {
        if (errorDiv.style.display === 'flex') {
            errorDiv.style.display = 'none';
        }
    }, 10000);
}

// ============================================
// ФУНКЦИИ ВАЛИДАЦИИ URL
// ============================================

function isValidUrl(string) {
    if (!string || string.trim() === '') return true; // Пустое поле - валидно

    try {
        const url = new URL(string);
        // Проверяем, что протокол http или https
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

    // Обновляем состояние кнопки
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

    // Проверяем вебхук
    if (webhookInput) {
        const webhookUrl = webhookInput.value.trim();
        if (webhookUrl.length > 0 && !isValidUrl(webhookUrl)) {
            isValid = false;
        }
    }

    // Проверяем пароль
    if (passwordInput) {
        const password = passwordInput.value.trim();
        if (password.length > 0 && (password.length < 4 || password.length > 16)) {
            isValid = false;
        }
    }

    // Управляем кнопкой
    confirmBtn.disabled = !isValid;

    if (confirmBtn.disabled) {
        confirmBtn.title = 'Исправьте ошибки в форме';
    } else {
        confirmBtn.title = '';
    }
}

// ============================================
// ОСНОВНЫЕ ФУНКЦИИ
// ============================================

async function uploadForPreview(file, textContent = null) {
    if (!file) return;
    hideErrorMessage();

    const formData = new FormData();
    formData.append('file', file);

    // НЕ переключаем состояние сразу, ждем ответ от сервера
    // Просто показываем индикатор загрузки в текущем состоянии
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

            // Показываем ошибку и возвращаемся в состояние загрузки
            showError(errorMsg, isRateLimit);

            // Возвращаем исходное состояние загрузки
            setState(State.UPLOAD);
            elements.previewContainer.innerHTML = '<div class="preview-placeholder">Выберите файл для предпросмотра</div>';

            return;
        }

        const data = await response.json();

        currentPreviewId = data.preview_id;
        currentFileData = data;

        // Только после успешного ответа переключаемся в PREVIEW
        setState(State.PREVIEW);

        elements.previewFilename.textContent = data.filename;
        elements.previewFilesize.textContent = data.size_formatted || formatFileSize(data.size);
        elements.previewType.textContent = getFileTypeName(data.mime_type);
        elements.previewIcon.textContent = data.icon || '📄';

        // Показываем поля для webhook и пароля при предпросмотре
        const webhookField = document.getElementById('webhookField');
        const passwordField = document.getElementById('passwordField');
        if (webhookField) webhookField.style.display = 'block';
        if (passwordField) passwordField.style.display = 'block';

        // Добавляем обработчики валидации
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

        // Если это текст из буфера - показываем textarea на всё поле
        if (textContent !== null && data.mime_type.startsWith('text/')) {
            isTextEditable = true;
            originalTextContent = textContent;
            elements.previewContainer.innerHTML = `
                <textarea class="text-editor-area" placeholder="Редактируйте текст..." spellcheck="false">${textContent}</textarea>
            `;
        } else {
            // Обычный предпросмотр
            isTextEditable = false;
            originalTextContent = null;
            let previewHtml = '';

            if (data.mime_type.startsWith('image/')) {
                previewHtml = `<img src="${data.preview_url}" alt="preview" class="preview-image">`;
            } else if (data.mime_type === 'application/pdf') {
                previewHtml = `<iframe src="${data.preview_url}" class="preview-iframe"></iframe>`;
            } else if (data.mime_type.startsWith('video/')) {
                previewHtml = `
                    <video controls class="preview-video">
                        <source src="${data.preview_url}" type="${data.mime_type}">
                    </video>
                `;
            } else if (data.mime_type.startsWith('audio/')) {
                previewHtml = `
                    <audio controls class="preview-audio">
                        <source src="${data.preview_url}" type="${data.mime_type}">
                    </audio>
                `;
            } else if (data.mime_type.startsWith('text/')) {
                previewHtml = `<iframe src="${data.preview_url}" class="preview-iframe"></iframe>`;
            } else {
                previewHtml = `<div class="preview-unsupported">
                    <p>Предпросмотр недоступен для этого типа файлов</p>
                    <p class="file-detail">Тип: ${data.mime_type}</p>
                </div>`;
            }

            elements.previewContainer.innerHTML = previewHtml;
        }

        // Валидируем форму после отображения
        validateForm();

    } catch (error) {
        console.error('Preview error:', error);
        showError('❌ Ошибка при загрузке файла: ' + error.message);

        // Возвращаемся в состояние загрузки
        setState(State.UPLOAD);
        elements.previewContainer.innerHTML = '<div class="preview-placeholder">Выберите файл для предпросмотра</div>';
    }
}

async function confirmUpload() {
    if (!currentPreviewId || !currentFileData) {
        alert('Ошибка: нет данных о файле');
        resetToUpload();
        return;
    }

    // Получаем значения из полей ввода
    const webhookInput = document.getElementById('webhookUrl');
    const passwordInput = document.getElementById('deletePassword');

    const webhookUrlValue = webhookInput?.value.trim() || '';
    const deletePasswordValue = passwordInput?.value.trim() || '';

    // Финальная валидация перед отправкой
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
            webhook_url: webhookUrlValue,  // используем значение из поля
            delete_password: deletePasswordValue  // используем значение из поля
        };

        // Если текст редактируемый - отправляем изменённое содержимое
        if (isTextEditable && originalTextContent !== null) {
            const textarea = elements.previewContainer.querySelector('.text-editor-area');
            if (textarea) {
                const editedText = textarea.value;
                requestBody.text_content = editedText;
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
        // используем data.token напрямую, не полагаясь на data.file_url
        const token = data.token;
        const filePath = `/view/${token}`;
        const fullUrl = baseUrl + filePath;

        elements.resultLink.value = fullUrl;

        // Сохраняем информацию о наличии вебхука
        const hasWebhook = data.has_webhook || false;

        // Обновляем ссылку для открытия файла
        if (hasWebhook) {
            // Для файлов с вебхуком убираем стандартную кнопку открытия
            elements.viewFileLink.style.display = 'none';

            // сохраняем правильный basePath
            const basePath = `/view/${token}`;

            // Показываем поле для ввода параметров
            showWebhookParamsField(fullUrl, basePath, token);
        } else {
            elements.viewFileLink.style.display = 'inline-flex';
            elements.viewFileLink.href = filePath;
            elements.viewFileLink.removeAttribute('data-webhook');
            elements.viewFileLink.removeAttribute('data-base-url');

            // Скрываем поле для ввода параметров, если оно было показано
            hideWebhookParamsField();
        }

        setState(State.RESULT);
        hideErrorMessage();

    } catch (error) {
        console.error('Confirm error:', error);
        showError(error.message || '❌ Ошибка при создании ссылки', error.isRateLimit);
        // Остаемся в состоянии предпросмотра
    } finally {
        setLoading(false);
    }
}

// ============================================
// ФУНКЦИИ ДЛЯ РАБОТЫ С ПАРАМЕТРАМИ ВЕБХУКА
// ============================================

function showWebhookParamsField(fullUrl, basePath, token) {
    // Проверяем, существует ли уже поле
    let paramsField = document.getElementById('webhookParamsField');

    if (!paramsField) {
        // Создаём поле для параметров
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
                <input type="text"
                       id="webhookParams"
                       class="webhook-params-input"
                       placeholder="system_id=123&secret_key=456"
                       value=""
                       oninput="validateWebhookParams()">
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

        // Вставляем перед result-actions
        if (resultActions) {
            resultCard.insertBefore(paramsField, resultActions);
        } else {
            resultCard.appendChild(paramsField);
        }

        // Добавляем обработчик для Enter в поле ввода
        const input = document.getElementById('webhookParams');
        if (input) {
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !document.getElementById('applyWebhookParamsBtn').disabled) {
                    applyWebhookParams(token);
                }
            });
        }
    } else {
        // Обновляем обработчик кнопки с новым токеном
        const applyBtn = document.getElementById('applyWebhookParamsBtn');
        if (applyBtn) {
            applyBtn.setAttribute('onclick', `applyWebhookParams('${token}')`);
        }
    }

    // Показываем поле и сбрасываем валидацию
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

    // Простейшая валидация: проверяем, что строка не пустая и содержит хотя бы один знак =
    const isValid = params.length > 0 && params.includes('=');

    applyBtn.disabled = !isValid;

    // Визуальная индикация
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

    // Дополнительная проверка перед открытием
    if (!params || !params.includes('=')) {
        showError('❌ Введите корректные параметры в формате key=value');
        return;
    }

    // формируем путь напрямую из токена
    let fullPath = `/view/${token}`;
    if (params) {
        if (params.startsWith('?')) {
            fullPath = `/view/${token}${params}`;
        } else {
            fullPath = `/view/${token}?${params}`;
        }
    }

    // Открываем в новой вкладке
    window.open(fullPath, '_blank');
}

// ============================================
// ФУНКЦИИ ДЛЯ КНОПОК ИНФОРМАЦИИ
// ============================================

function showInfo(type) {
    // Скрываем все открытые попапы
    hideAllInfo();

    // Показываем нужный
    const info = document.getElementById(type + 'Info');
    if (info) {
        info.classList.remove('hidden');

        // Закрытие при клике вне попапа
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
    infos.forEach(info => {
        info.classList.add('hidden');
    });
}

// Закрытие по Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideAllInfo();
    }
});

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ
// ============================================

// Выбор файла через кнопку "Выбрать файл"
if (elements.selectFileBtn) {
    elements.selectFileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.fileInput.click();
    });
}

// Выбор файла через input
elements.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) uploadForPreview(file);
    hideErrorMessage();
});

// Drag & Drop
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

// Клик по зоне загрузки открывает выбор файла
elements.dropZone.addEventListener('click', (e) => {
    elements.fileInput.click();
    hideErrorMessage();
});

// Обработка вставки из буфера (глобально)
document.addEventListener('paste', handlePaste);

// Клик по кнопке "Вставить из буфера"
if (elements.pasteTrigger) {
    elements.pasteTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        activatePaste();
    });
}

// Кнопки
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

// Кнопка копирования
if (elements.copyBtn) {
    elements.copyBtn.addEventListener('click', copyLinkToClipboard);
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================

resetToUpload();

// Защита от случайной перезагрузки
window.addEventListener('beforeunload', (e) => {
    if (currentState === State.PREVIEW && currentPreviewId) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// Сохраняем автора (для страницы просмотра)
document.addEventListener('DOMContentLoaded', function() {
    const authorInputs = document.querySelectorAll('input[name="author"]');
    const savedAuthor = localStorage.getItem('aspic_author');

    if (savedAuthor) {
        authorInputs.forEach(input => {
            input.value = savedAuthor;
        });
    }

    authorInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.value && this.value.trim()) {
                localStorage.setItem('aspic_author', this.value.trim());
            }
        });
    });
});