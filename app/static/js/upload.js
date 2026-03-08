// Глобальные переменные
let uploadArea, fileInput, progressContainer, resultContainer, errorContainer;
let progressBar, progressFill, progressText, fileUrl, errorText;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что мы на главной странице с формой загрузки
    uploadArea = document.getElementById('uploadArea');
    if (!uploadArea) return;

    fileInput = document.getElementById('fileInput');
    progressContainer = document.getElementById('progressContainer');
    resultContainer = document.getElementById('resultContainer');
    errorContainer = document.getElementById('errorContainer');
    progressBar = document.getElementById('progressBar');
    progressFill = document.querySelector('.progress-fill');
    progressText = document.getElementById('progressText');
    fileUrl = document.getElementById('fileUrl');
    errorText = document.getElementById('errorText');

    // Клик по области открывает диалог выбора файла
    uploadArea.addEventListener('click', (e) => {
        if (e.target.tagName !== 'INPUT') {
            fileInput.click();
        }
    });

    // Drag & drop события
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
            uploadFile(files[0]);
        }
    });

    // Выбор файла через диалог
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadFile(fileInput.files[0]);
        }
    });
});

// Функция загрузки файла
async function uploadFile(file) {
    // Показываем прогресс
    uploadArea.style.display = 'none';
    progressContainer.style.display = 'block';

    // Сброс прогресса
    progressFill.style.width = '0%';
    progressText.textContent = 'Загрузка...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Используем XMLHttpRequest для отслеживания прогресса
        const xhr = new XMLHttpRequest();

        // Отслеживание прогресса
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                progressFill.style.width = percent + '%';
                progressText.textContent = `Загрузка... ${Math.round(percent)}%`;
            }
        });

        // Создаём Promise для ожидания ответа
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

        // Успешная загрузка
        progressContainer.style.display = 'none';
        resultContainer.style.display = 'block';

        // Формируем полный URL
        const url = window.location.origin + response.url;
        fileUrl.value = url;

    } catch (error) {
        // Ошибка
        progressContainer.style.display = 'none';
        errorContainer.style.display = 'block';

        try {
            const errorData = JSON.parse(error.message);
            errorText.textContent = errorData.detail || 'Неизвестная ошибка';
        } catch {
            errorText.textContent = error.message;
        }
    }
}

// Сброс формы загрузки
function resetUpload() {
    uploadArea.style.display = 'block';
    errorContainer.style.display = 'none';
    fileInput.value = '';
}

// Копирование ссылки в буфер обмена
function copyUrl() {
    const urlInput = document.getElementById('fileUrl');
    urlInput.select();
    urlInput.setSelectionRange(0, 99999);

    try {
        document.execCommand('copy');
        alert('Ссылка скопирована!');
    } catch (err) {
        alert('Не удалось скопировать ссылку');
    }
}