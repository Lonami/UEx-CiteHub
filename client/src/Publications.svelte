<script>
    import Publication from './Publication.svelte';

    import { get_publications } from './rest.js';
</script>

<style>
    table {
        border-collapse: collapse;
        max-width: 1200px;
    }

    th {
        font-variant: small-caps;
        background-color: #eee;
        padding: 2px 4px;
    }
</style>

<div class="publications">
    {#await get_publications()}
        <p>Loading publications…</p>
    {:then result}
        <h2>Metrics</h2>
        <ul>
            <li>h-index: <strong>{result.h_index}</strong></li>
        </ul>
        <table>
            <thead>
                <tr>
                    <th>Source</th>
                    <th>Title</th>
                    <th>Cited by</th>
                    <!-- <th>Year</th> -->
                </tr>
            </thead>
            <tbody>
                {#each result.publications as publication (publication.id)}
                    <Publication {publication}/>
                {/each}
            </tbody>
        </table>
    {:catch error}
        <p>Failed to fetch dialogs: {error.message}</p>
    {/await}
</div>
