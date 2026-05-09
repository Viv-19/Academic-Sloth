// The URL of our Express Backend API
const API_URL = 'http://localhost:3000/api/auth';

export const auth = {
    async signin(formData) {
        try {
            const response = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: formData.email, password: formData.password })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Login failed. Please check your credentials.');
                return;
            }

            localStorage.setItem('token', data.data.token);
            localStorage.setItem('user', JSON.stringify(data.data.user));
            window.location.href = 'dashboard.html';
        } catch (error) {
            console.error('Error during signin:', error);
            alert('A network error occurred.');
        }
    },

    async signup(formData) {
        try {
            const response = await fetch(`${API_URL}/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: formData.fullname,
                    email: formData.email,
                    password: formData.password
                })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Signup failed.');
                return;
            }

            // We don't get a token yet. We just save the email and redirect to verify page.
            localStorage.setItem('pending_email', formData.email);
            window.location.href = 'verify.html';
        } catch (error) {
            console.error('Error during signup:', error);
            alert('A network error occurred.');
        }
    },

    async verifyOtp(formData) {
        try {
            const response = await fetch(`${API_URL}/verify-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: formData.email, otp: formData.otp })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Verification failed.');
                return;
            }

            localStorage.setItem('token', data.data.token);
            localStorage.setItem('user', JSON.stringify(data.data.user));
            window.location.href = 'dashboard.html';
        } catch (error) {
            console.error('Error during verification:', error);
            alert('A network error occurred.');
        }
    },

    async forgotPassword(email) {
        try {
            const response = await fetch(`${API_URL}/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Request failed.');
                return;
            }

            window.location.href = 'reset-password.html';
        } catch (error) {
            console.error('Error during forgot password:', error);
            alert('A network error occurred.');
        }
    },

    async resetPassword(formData) {
        try {
            const response = await fetch(`${API_URL}/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: formData.email,
                    otp: formData.otp,
                    newPassword: formData.newPassword
                })
            });
            const data = await response.json();

            if (!response.ok) {
                alert(data.message || 'Reset failed.');
                return;
            }

            window.location.href = 'signin.html';
        } catch (error) {
            console.error('Error during reset password:', error);
            alert('A network error occurred.');
        }
    }
};
