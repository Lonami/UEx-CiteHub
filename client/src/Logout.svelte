<script>
    import { logout_user } from './rest.js';
    import { user_token } from './stores.js';

    let text = 'Logging out…';

    async function logout() {
        try {
            await logout_user();
        } catch (e) {
            text = `Error: ${e.message}. <a href="/logout">Try again</a>.`;
            return;
        }

        user_token.set(null);
        window.location.replace('/login');
        text = `Logout success. <a href="/login">Login again</a>.`;
    }

    logout();
</script>

<p>{@html text}</p>
