// Глобальные переменные
let uploadArea, fileInput, progressContainer, resultContainer, errorContainer;
let progressBar, progressFill, progressText, fileUrl, errorText;
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB
const UPLOAD_COOLDOWN = 10; // секунд между загрузками с одного IP

// Хранилище времени последней загрузки для IP
const lastUploadTime = new Map();

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    uploadArea = document.getElementById('uploadArea');

    addPasteButton();

    if (!uploadArea) {
        setupPasteHandler();
        return;
    }

    fileInput = document.getElementById('fileInput');
    progressContainer = document.getElementById('progressContainer');
    resultContainer = document.getElementById('resultContainer');
    errorContainer = document.getElementById('errorContainer');
    progressBar = document.getElementById('progressBar');
    progressFill = document.querySelector('.progress-fill');
    progressText = document.getElementById('progressText');
    fileUrl = document.getElementById('fileUrl');
    errorText = document.getElementById('errorText');

    // Кнопки в результате загрузки
    addResultButtons();

    uploadArea.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT') {
            fileInput.click();
        }
    });

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
            checkUploadCooldown().then(() => uploadFile(files[0]));
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            checkUploadCooldown().then(() => uploadFile(fileInput.files[0]));
        }
    });

    setupPasteHandler();
});

// Проверка временного ограничения
async function checkUploadCooldown() {
    // В реальном приложении здесь должен быть запрос к серверу
    // Но для демо используем локальное хранилище
    const lastTime = lastUploadTime.get('current') || 0;
    const now = Date.now();
    const timeLeft = UPLOAD_COOLDOWN * 1000 - (now - lastTime);

    if (timeLeft > 0) {
        const secondsLeft = Math.ceil(timeLeft / 1000);
        throw new Error(`Подождите ${secondsLeft} сек. перед следующей загрузкой`);
    }

    lastUploadTime.set('current', now);
}

// Добавление кнопок действий после загрузки
function addResultButtons() {
    if (!resultContainer) return;

    // Создаём контейнер для кнопок, если его нет
    let actionButtons = document.getElementById('resultActions');
    if (!actionButtons) {
        actionButtons = document.createElement('div');
        actionButtons.id = 'resultActions';
        actionButtons.className = 'result-actions';
        resultContainer.appendChild(actionButtons);
    }

    // Кнопка "Открыть ссылку"
    const openBtn = document.createElement('button');
    openBtn.className = 'action-btn open-btn';
    openBtn.innerHTML = '🔗 Открыть ссылку';
    openBtn.onclick = () => {
        const url = fileUrl.value;
        if (url) window.open(url, '_blank');
    };

    // Кнопка "Загрузить новый файл"
    const newBtn = document.createElement('button');
    newBtn.className = 'action-btn new-btn';
    newBtn.innerHTML = '📤 Загрузить новый файл';
    newBtn.onclick = resetUpload;

    actionButtons.innerHTML = ''; // Очищаем перед добавлением
    actionButtons.appendChild(openBtn);
    actionButtons.appendChild(newBtn);
}

// Функция добавления кнопок вставки из буфера
function addPasteButton() {
    let buttonContainer = document.getElementById('pasteButtonContainer');
    if (!buttonContainer) {
        buttonContainer = document.createElement('div');
        buttonContainer.id = 'pasteButtonContainer';
        buttonContainer.className = 'paste-button-container';

        const uploadContainer = document.querySelector('.upload-container');
        if (uploadContainer) {
            uploadContainer.appendChild(buttonContainer);
        } else {
            document.body.appendChild(buttonContainer);
        }
    }

    // Очищаем контейнер перед добавлением
    buttonContainer.innerHTML = '';

    const imagePasteBtn = document.createElement('button');
    imagePasteBtn.className = 'paste-btn image-paste-btn';
    imagePasteBtn.innerHTML = '📷 Вставить изображение из буфера';
    imagePasteBtn.onclick = () => pasteFromClipboard('image');

    const textPasteBtn = document.createElement('button');
    textPasteBtn.className = 'paste-btn text-paste-btn';
    textPasteBtn.innerHTML = '📝 Вставить текст из буфера';
    textPasteBtn.onclick = () => pasteFromClipboard('text');

    buttonContainer.appendChild(imagePasteBtn);
    buttonContainer.appendChild(textPasteBtn);
}

// Функция вставки из буфера
async function pasteFromClipboard(type) {
    try {
        // Проверяем ограничение по времени
        await checkUploadCooldown();

        // Запрашиваем доступ к буферу обмена
        const clipboardItems = await navigator.clipboard.read();

        for (const item of clipboardItems) {
            if (type === 'image') {
                for (const type of item.types) {
                    if (type.startsWith('image/')) {
                        const blob = await item.getType(type);
                        const now = new Date();
                        const timestamp = now.toISOString()
                            .replace(/[-:]/g, '')
                            .replace(/\..+/, '')
                            .replace('T', '_');
                        const filename = `clipboard_image_${timestamp}.${type.split('/')[1] || 'png'}`;
                        const file = new File([blob], filename, { type: type });
                        await uploadFile(file);
                        return;
                    }
                }
                alert('В буфере нет изображения');
            } else if (type === 'text') {
                for (const type of item.types) {
                    if (type === 'text/plain') {
                        const blob = await item.getType(type);
                        const text = await blob.text();

                        const now = new Date();
                        const timestamp = now.toISOString()
                            .replace(/[-:]/g, '')
                            .replace(/\..+/, '')
                            .replace('T', '_');
                        const filename = `clipboard_text_${timestamp}.txt`;

                        const file = new File([text], filename, { type: 'text/plain' });
                        await uploadFile(file);
                        return;
                    }
                }
                alert('В буфере нет текста');
            }
        }
    } catch (err) {
        console.error('Ошибка доступа к буферу обмена:', err);

        if (err.message.includes('Подождите')) {
            alert(err.message);
            return;
        }

        // Fallback для текста
        if (type === 'text') {
            const text = prompt('Вставьте текст вручную:');
            if (text) {
                try {
                    await checkUploadCooldown();
                    const now = new Date();
                    const timestamp = now.toISOString()
                        .replace(/[-:]/g, '')
                        .replace(/\..+/, '')
                        .replace('T', '_');
                    const filename = `clipboard_text_${timestamp}.txt`;
                    const file = new File([text], filename, { type: 'text/plain' });
                    await uploadFile(file);
                } catch (cooldownErr) {
                    alert(cooldownErr.message);
                }
            }
        } else {
            alert('Не удалось получить доступ к буферу обмена. Используйте Ctrl+V');
        }
    }
}

// Функция настройки обработчика вставки из буфера
function setupPasteHandler() {
    document.addEventListener('paste', async function(e) {
        try {
            await checkUploadCooldown();
        } catch (err) {
            alert(err.message);
            return;
        }

        const items = e.clipboardData.items;

        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                if (window.location.pathname.startsWith('/v/')) {
                    if (!confirm('Вставить изображение из буфера как новый файл?')) {
                        return;
                    }
                }

                const file = items[i].getAsFile();
                const now = new Date();
                const timestamp = now.toISOString()
                    .replace(/[-:]/g, '')
                    .replace(/\..+/, '')
                    .replace('T', '_');
                const ext = items[i].type.split('/')[1] || 'png';
                const filename = `clipboard_image_${timestamp}.${ext}`;
                const newFile = new File([file], filename, { type: file.type });
                await uploadFile(newFile);
                break;
            }

            if (items[i].type === 'text/plain') {
                if (window.location.pathname.startsWith('/v/')) {
                    if (!confirm('Вставить текст из буфера как новый файл?')) {
                        return;
                    }
                }

                items[i].getAsString(async (text) => {
                    const now = new Date();
                    const timestamp = now.toISOString()
                        .replace(/[-:]/g, '')
                        .replace(/\..+/, '')
                        .replace('T', '_');
                    const filename = `clipboard_text_${timestamp}.txt`;
                    const file = new File([text], filename, { type: 'text/plain' });
                    await uploadFile(file);
                });
                break;
            }
        }
    });
}

// Функция загрузки файла
async function uploadFile(file) {
    // Проверка размера
    if (file.size > MAX_FILE_SIZE) {
        const errorMsg = `Файл слишком большой (макс. ${MAX_FILE_SIZE / 1024 / 1024} MB)`;

        if (uploadArea && errorContainer && errorText) {
            uploadArea.style.display = 'block';
            errorContainer.style.display = 'block';
            errorText.textContent = errorMsg;
        } else {
            alert(errorMsg);
        }
        return;
    }

    if (uploadArea && progressContainer) {
        uploadArea.style.display = 'none';
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Загрузка...';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && progressFill && progressText) {
                const percent = (e.loaded / e.total) * 100;
                progressFill.style.width = percent + '%';
                progressText.textContent = `Загрузка... ${Math.round(percent)}%`;
            }
        });

        const response = await new Promise((resolve, reject) => {
            xhr.open('POST', '/api/upload');

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(xhr.responseText || 'Ошибка загрузки'));
                }
            };

            xhr.onerror = () => reject(new Error('Ошибка сети'));
            xhr.send(formData);
        });

        if (progressContainer) progressContainer.style.display = 'none';

        if (resultContainer && fileUrl) {
            resultContainer.style.display = 'block';
            const url = window.location.origin + response.url;
            fileUrl.value = url;

            // Обновляем кнопки действий
            addResultButtons();
        } else {
            const url = window.location.origin + response.url;
            alert(`Файл успешно загружен!\nСсылка: ${url}`);

            if (confirm('Перейти к файлу?')) {
                window.location.href = response.url;
            }
        }

    } catch (error) {
        let errorMessage = 'Неизвестная ошибка';
        try {
            const errorData = JSON.parse(error.message);
            errorMessage = errorData.detail || errorMessage;
        } catch {
            errorMessage = error.message;
        }

        if (progressContainer) progressContainer.style.display = 'none';

        if (errorContainer && errorText) {
            errorContainer.style.display = 'block';
            errorText.textContent = errorMessage;
        } else {
            alert(`Ошибка загрузки: ${errorMessage}`);
        }
    }
}

// Сброс формы загрузки
function resetUpload() {
    if (uploadArea) uploadArea.style.display = 'block';
    if (errorContainer) errorContainer.style.display = 'none';
    if (resultContainer) resultContainer.style.display = 'none';
    if (fileInput) fileInput.value = '';
}

// Копирование ссылки в буфер обмена
function copyUrl() {
    const urlInput = document.getElementById('fileUrl');
    if (!urlInput) return;

    urlInput.select();
    urlInput.setSelectionRange(0, 99999);

    try {
        document.execCommand('copy');
        alert('Ссылка скопирована!');
    } catch (err) {
        alert('Не удалось скопировать ссылку');
    }
}

window.uploadFile = uploadFile;