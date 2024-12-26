// Flash message handling
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    setTimeout(function() {
        const flashMessages = document.querySelectorAll('.flash');
        flashMessages.forEach(function(message) {
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 300);
        });
    }, 5000);

    // Password visibility toggle
    const togglePassword = document.querySelector('.toggle-password');
    if (togglePassword) {
        togglePassword.addEventListener('click', function() {
            const passwordInput = document.querySelector('#client_secret');
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.textContent = type === 'password' ? '👁️' : '🔒';
        });
    }

    // Form validation
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(event) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error');
                } else {
                    field.classList.remove('error');
                }
            });

            if (!isValid) {
                event.preventDefault();
                alert('Bitte füllen Sie alle erforderlichen Felder aus.');
            }
        });
    }
});

// Image preview functionality
function previewImage(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        const preview = document.querySelector('#imagePreview');
        
        reader.onload = function(e) {
            preview.src = e.target.result;
            preview.style.display = 'block';
        };

        reader.readAsDataURL(input.files[0]);
    }
}

// Copy to clipboard functionality
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('In die Zwischenablage kopiert!');
    }).catch(err => {
        console.error('Fehler beim Kopieren:', err);
    });
}

function addNewPost() {
    // Your function implementation here
}

function removePost(btn) {
    // Your function implementation here
}

function updatePreviewListeners(postCard) {
    // Your function implementation here
}

FB.login(function(response) {
    if (response.status === 'connected') {
        const returnedState = new URLSearchParams(window.location.search).get('state');
        const savedState = sessionStorage.getItem('fb_state');
        
        if (returnedState && savedState && returnedState === savedState) {
            window.location.href = '/auth/facebook/callback?access_token=' + response.authResponse.accessToken + '&state=' + state;
        } else {
            console.error('State parameter mismatch');
            alert('Sicherheitsfehler: Ungültiger State-Parameter');
        }
    }
}, {
    scope: 'instagram_basic',
    auth_type: 'rerequest',
    return_scopes: true
});
