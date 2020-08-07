<script>
import { onMount } from 'svelte';
import { get_user_profile, update_user_profile, force_merge } from './rest.js';

let source_form;
let submit_button;

let last_error = null;

async function save_details() {
    submit_button.disabled = true;
    submit_button.value = 'Saving…';
    try {
        let data = {}
        for (let [key, value] of new FormData(source_form).entries()) {
            data[key] = value;
        }
        let result = await update_user_profile(data);
        if (result.errors.length !== 0) {
            let error = 'Some errors occured:';
            for (let e of result.errors) {
                error += `\nFailed to update ${e.namespace}.${e.key}: ${e.reason}`;
            }
            last_error = {message: error};
        }
    } catch (e) {
        last_error = e;
    } finally {
        submit_button.disabled = false;
        submit_button.value = 'Save';
    }
}
</script>

<style>
</style>

{#if last_error !== null}
    <p>An error occured: {last_error.message}</p>
{/if}

<button on:click={force_merge}>Force merge</button>

{#await get_user_profile()}
    <p>Loading external source fields…</p>
{:then profile}
    <p>Logged in as <em>{profile.username}</em>.</p>
    <form bind:this={source_form} on:submit|preventDefault={save_details}>
        {#each profile.sources as source}
            <div>
                <label for="es-{source.key}">Value for {source.key}:</label>
                <input id="es-{source.key}" name={source.key} value={source.value}>
                <p>{@html source.description}</p>
            </div>
        {/each}
        <div>
            <input bind:this={submit_button} type="submit" value="Save">
        </div>
    </form>
    <!-- TODO allow deleting account and updating password -->
{:catch e}
    <p>Failed to load external source fields: {e.message}</p>
{/await}
