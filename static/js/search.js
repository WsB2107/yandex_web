// Обработчик для кнопки "Добавить в друзья"
document.addEventListener('DOMContentLoaded', function() {
    const addFriendButtons = document.querySelectorAll('.add-friend-btn');
    addFriendButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            const username = this.getAttribute('data-username');
            
            fetch('/api/add_friend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Меняем кнопку на "Запрос отправлен"
                    button.textContent = 'Запрос отправлен';
                    button.disabled = true;
                    button.classList.remove('btn-small');
                    button.classList.add('btn-disabled');
                    // Показываем сообщение
                    showNotification(`Запрос в друзья отправлен пользователю ${username}`);
                } else {
                    // Показываем ошибку
                    showNotification(data.error || 'Не удалось отправить запрос', 'error');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                showNotification('Произошла ошибка при отправке запроса', 'error');
            });
        });
    });

    // Функция для показа уведомлений
    function showNotification(message, type = 'success') {
        // Создаем элемент уведомления
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Добавляем в body
        document.body.appendChild(notification);
        
        // Удаляем через 3 секунды
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});