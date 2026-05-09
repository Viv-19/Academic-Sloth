// The URL of our Express Backend API
const API_URL = 'http://localhost:3000/api/auth';

export const auth = {
    /**
     * Sends Login Request to the Backend
     */
    async signin(formData) {
        try {
            const response = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: formData.email,
                    password: formData.password
                })
            });

            const data = await response.json();

            // If the status code is not in the 200 range (e.g. 401 Unauthorized)
            if (!response.ok) {
                alert(data.message || 'Login failed. Please check your credentials.');
                return;
            }

            // Success! Save the token to the browser's localStorage
            localStorage.setItem('token', data.data.token);
            localStorage.setItem('user', JSON.stringify(data.data.user));

            alert('Logged in successfully! Welcome to Academic Sloth.');
            
            // Redirect to the dashboard
            window.location.href = 'dashboard.html';

        } catch (error) {
            console.error('Error during signin:', error);
            alert('A network error occurred. Is the backend server running?');
        }
    },

    /**
     * Sends Signup Request to the Backend
     */
    async signup(formData) {
        try {
            const response = await fetch(`${API_URL}/signup`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: formData.fullname, // The HTML uses 'fullname', backend expects 'name'
                    email: formData.email,
                    password: formData.password
                })
            });

            const data = await response.json();

            // If the status code is not in the 200 range (e.g. 409 Conflict)
            if (!response.ok) {
                alert(data.message || 'Signup failed.');
                return;
            }

            // Success! Save the token to the browser's localStorage
            localStorage.setItem('token', data.data.token);
            localStorage.setItem('user', JSON.stringify(data.data.user));

            alert('Account created successfully! Welcome to Academic Sloth.');
            
            // Redirect to the dashboard
            window.location.href = 'dashboard.html';

        } catch (error) {
            console.error('Error during signup:', error);
            alert('A network error occurred. Is the backend server running?');
        }
    }
};
