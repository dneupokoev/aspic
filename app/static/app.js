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
                    <p>Предпросмотр недоступен</p>
                    <p class="file-detail">Тип: ${data.mime_type}</p>
                </div>`;
            }

            elements.previewContainer.innerHTML = previewHtml;
        }

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
    webhookUrl = document.getElementById('webhookUrl')?.value || '';
    deletePassword = document.getElementById('deletePassword')?.value || '';

    // Валидация
    if (webhookUrl && (webhookUrl.length < 4 || webhookUrl.length > 1024)) {
        alert('URL вебхука должен быть от 4 до 1024 символов');
        return;
    }

    if (deletePassword && (deletePassword.length < 4 || deletePassword.length > 16)) {
        alert('Пароль должен быть от 4 до 16 символов');
        return;
    }

    setLoading(true);

    try {
        const requestBody = {
            preview_id: currentPreviewId,
            filename: currentFileData.filename,
            mime_type: currentFileData.mime_type,
            size: currentFileData.size,
            webhook_url: webhookUrl,
            delete_password: deletePassword
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
        const filePath = data.file_url || `/view/${data.token}`;
        const fullUrl = baseUrl + filePath;

        elements.resultLink.value = fullUrl;
        elements.viewFileLink.href = filePath;

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