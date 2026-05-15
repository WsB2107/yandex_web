// Обработчики для кнопок принятия и отклонения заявок в друзья
document.addEventListener('DOMContentLoaded', function() {
    // Обработчик для кнопки "Принять"
    const acceptButtons = document.querySelectorAll('.accept-friend');
    acceptButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            
            fetch('/api/accept_friend', {
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
                    // Удаляем элемент заявки
                    this.closest('.request-item').remove();
                    
                    // Показываем сообщение
                    showNotification('Заявка в друзья принята');
                    
                    // Если больше нет заявок, показываем сообщение
                    if (document.querySelectorAll('.request-item').length === 0) {
                        document.querySelector('.requests-grid').innerHTML = '<p class="empty-message">Нет входящих заявок</p>';
                    }
                } else {
                    // Показываем ошибку
                    showNotification(data.error || 'Не удалось принять заявку', 'error');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                showNotification('Произошла ошибка при принятии заявки', 'error');
            });
        });
    });
    
    // Обработчик для кнопки "Отклонить"
    const rejectButtons = document.querySelectorAll('.reject-friend');
    rejectButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const userId = this.getAttribute('data-user-id');
            
            fetch('/api/reject_friend', {
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
                    // Удаляем элемент заявки
                    this.closest('.request-item').remove();
                    
                    // Показываем сообщение
                    showNotification('Заявка в друзья отклонена');
                    
                    // Если больше нет заявок, показываем сообщение
                    if (document.querySelectorAll('.request-item').length === 0) {
                        document.querySelector('.requests-grid').innerHTML = '<p class="empty-message">Нет входящих заявок</p>';
                    }
                } else {
                    // Показываем ошибку
                    showNotification(data.error || 'Не удалось отклонить заявку', 'error');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                showNotification('Произошла ошибка при отклонении заявки', 'error');
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