document.addEventListener('DOMContentLoaded', () => {
    console.log('JavaScript is working!');
});

function processText() {
    const text = document.getElementById('inputText').value;

    fetch('/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: text })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('result').textContent = 'Result: ' + data.result;
    });
}
