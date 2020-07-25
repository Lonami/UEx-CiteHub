<script>
    import Publication from './Publication.svelte';

    import { get_publications } from './rest.js';

    let sort_by = {key: null, rev: false};

    // bit ugly because we want sorting to work with async; probably there is a better way
    let pubs;
    let publications = null;
    async function load_publications() {
        pubs = await get_publications();
        set_sort(null);
    }

    function set_sort(key) {
        if (sort_by.key === key) {
            sort_by.rev = !sort_by.rev;
        } else {
            sort_by.key = key;
            sort_by.rev = false;
        }

        if (sort_by.key === null) {
            publications = pubs.publications;
        } else {
            let value = sort_by.rev ? -1 : 1;
            let sorted = pubs.publications.slice();
            sorted.sort(function(a, b) {
                if (a[sort_by.key] < b[sort_by.key]) {
                    return -value;
                } else if (a[sort_by.key] > b[sort_by.key]) {
                    return value;
                } else {
                    return 0;
                }
            });
            publications = sorted;
        }
    }
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
        cursor: pointer;
    }
</style>

<div class="publications">
    {#await load_publications()}
        <p>Loading publications…</p>
    {:then _}
        <h2>Metrics</h2>
        <ul>
            <li>h-index: <strong>{pubs.h_index}</strong></li>
        </ul>
        <table>
            <thead>
                <tr>
                    <th on:click={_ => set_sort(null)}>Source</th>
                    <!-- TODO would be nice to link to the website and see the entry on the corresponding source -->
                    <th on:click={_ => set_sort("name")}>Title</th>
                    <th on:click={_ => set_sort("cites")}>Cited by</th>
                    <!-- <th>Year</th> -->
                </tr>
            </thead>
            <tbody>
                {#each publications as publication}
                    <Publication {publication}/>
                {/each}
            </tbody>
        </table>
    {:catch error}
        <p>Failed to fetch dialogs: {error.message}</p>
    {/await}
</div>
