<script>
import { onMount } from 'svelte';
import { get_sources, save_sources } from './rest.js';

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
        await save_sources(data);
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

{#await get_sources()}
    <p>Loading external source fields…</p>
{:then sources}
    <form bind:this={source_form} on:submit|preventDefault={save_details}>
        {#each sources as source}
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
{:catch e}
    <p>Failed to load external source fields: {e.message}</p>
{/await}
