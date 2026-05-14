let currentIndex = 0;
const cards = document.querySelectorAll('.tinder-card');
if (cards.length > 0) initCard(cards[0]);

function initCard(card) {
    card.style.display = 'block';
    card.style.zIndex = 100;
    // Добавьте touch/mouse drag логику по желанию
}

document.getElementById('like').addEventListener('click', () => swipe(1));
document.getElementById('dislike').addEventListener('click', () => swipe(-1));
document.getElementById('trackTitle').innerText = currentTrack.title;
document.getElementById('trackArtist').innerText = currentTrack.artist;
document.getElementById('trackGenre').innerText = currentTrack.genre;
function swipe(direction) {
    if (currentIndex >= cards.length) return;
    const card = cards[currentIndex];
    const trackId = card.dataset.id;
    const action = direction > 0 ? '/like/' : '/dislike/';
    fetch(action + trackId, { method: 'POST' }).then(r => r.json()).then(d => {
        // анимация улетания
        card.style.transition = '0.3s';
        card.style.transform = `translateX(${direction * 300}px) rotate(${direction * 20}deg)`;
        setTimeout(() => {
            card.style.display = 'none';
            currentIndex++;
            if (currentIndex < cards.length) initCard(cards[currentIndex]);
            else alert('Подборка закончилась! Обновите страницу.');
        }, 300);
    });
}