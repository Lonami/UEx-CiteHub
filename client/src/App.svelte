<script>
    import { fade } from 'svelte/transition';

    import ProfileInfo from './ProfileInfo.svelte';
    import ProfileSettings from './ProfileSettings.svelte';
    import Publications from './Publications.svelte';

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

<h1>UEx-CiteHub</h1>
<ProfileInfo/>

<button on:click={e => settings_open = true}>Settings</button>

<Publications/>

{#if settings_open}
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
{/if}
