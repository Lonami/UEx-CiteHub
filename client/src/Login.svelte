<script>
    import { register_user, login_user } from './rest.js';
    import { logged_in } from './stores.js';

    export let register;

    let is_logged;
    const unsubscribe = logged_in.subscribe(value => {
        is_logged = value;
    });

    let form;
    let confirm_password = null;
    let error = null;

    function set_form_enabled(enabled) {
        for (let input of form.getElementsByTagName('input')) {
            input.disabled = !enabled;
        }
    }

    async function handle_submit(event) {
        if (confirm_password !== null && event.target.password.value !== confirm_password.value) {
            error = {message: "passwords don't match"};
            return;
        }

        set_form_enabled(false);

        let logged = false;
        try {
            if (register) {
                logged = await register_user(
                    event.target.username.value,
                    event.target.password.value
                );
            } else {
                logged = await login_user(
                    event.target.username.value,
                    event.target.password.value
                )
            }
        } catch (e) {
            error = e;
            return;
        } finally {
            set_form_enabled(true);
        }

        logged_in.set(logged);
        window.location.replace('/metrics');
    }
</script>

<style>
    div.center {
        max-width: 20em;
        margin: 0 auto;
        padding: 2em;
    }

    form div {
        display: grid;
        grid-template-columns: max-content max-content;
        grid-gap: 1em;
        width: 100%;
    }

    input {
        width: 100%;
    }

    input[type=submit] {
        margin-top: 1em;
        cursor: pointer;
    }
</style>

<div class="center">
    {#if error !== null}
        <p><strong>Error:</strong> {error.message}</p>
    {/if}

    {#if is_logged}
        <p>
            You're already logged in. If you want to register or login to another
            account you must <a href="/logout">logout</a> first.
        </p>
    {:else}
        <form bind:this={form} on:submit|preventDefault={handle_submit}>
            <div>
                <label for="username">Username: </label>
                <input type="text" name="username" id="username" required>
                <label for="password">Password: </label>
                <input type="password" name="password" id="password" required>
                {#if register}
                    <label for="confirm_password">Confirm password: </label>
                    <input bind:this={confirm_password} type="password" id="confirm_password" required>
                {/if}
            </div>
            <input type="submit" value={register ? "Register" : "Login"}>
        </form>
    {/if}
</div>
