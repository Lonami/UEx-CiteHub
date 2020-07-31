<script>
    import { fade } from 'svelte/transition';

    import ProfileSettings from './ProfileSettings.svelte';
    import Publications from './Publications.svelte';
    import Register from './Register.svelte';
    import Navigation from './Navigation.svelte';

    import { force_merge } from './rest.js';

    let settings_open = false;

    function clicked_out_settings(event) {
        if (event.target === this) {
            settings_open = false;
        }
    }
</script>

<style>
.settings {
    position: fixed;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(255, 255, 255, 0.7);
    padding: 1em;
}

.settings div {
    max-width: 40em;
    max-height: 100%;
    overflow-y: auto;
    margin: auto;
    background-color: #fff;
    padding: 1em;
    position: relative;
    border: 1px solid #000;
}

.close {
    width: 24px;
    height: 24px;
    cursor: pointer;
    padding: 0;
    background: none;
    border: none;
    position: absolute;
    right: 16px;
}

.close span {
    clip: rect(0 0 0 0);
    height: 1px;
    width: 1px;
    overflow: hidden;
    position: absolute;
}

.close svg {
    width: 24px;
    height: 24px;
}
</style>

<Navigation/>

<button on:click={e => settings_open = true}>Settings</button>
<button on:click={force_merge}>Force merge</button>

{#if window.location.pathname === '/'}
    <p>Welcome…</p>
{:else if window.location.pathname === '/register'}
    <p>Register…</p>
{:else if window.location.pathname === '/login'}
    <p>Login…</p>
{:else if window.location.pathname === '/metrics'}
    <p>Metrics…</p>
{:else if window.location.pathname === '/publications'}
    <Publications/>
{:else if window.location.pathname === '/settings'}
    <div class="settings" on:click={clicked_out_settings} transition:fade={{duration: 100}}>
        <div>
            <button type="button" class="close" on:click={e => settings_open = false}>
                <span>Close settings</span>
                <svg xmlns="http://www.w3.org/2000/svg" role="presentation" viewBox="0 0 24 24">
                    <path d="M0 0 L24 24 M0 24 L24 0" stroke="#000"/>
                </svg>
            </button>
            <ProfileSettings/>
        </div>
    </div>
{:else if window.location.pathname === '/logout'}
    <p>Logging out…</p>
{:else}
    <h2>404</h2>
    <p>No such page exists at {window.location.pathname}</p>
{/if}
