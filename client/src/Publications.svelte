<script>
    import Publication from './Publication.svelte';
    import Chart from './Chart.svelte';

    import { get_publications } from './rest.js';

    let sort_by = {key: null, rev: false};
    function set_sort(key) {
        if (sort_by.key === key) {
            sort_by.rev = !sort_by.rev;
        } else {
            sort_by = {key: key, rev: false};
        }
    }

    $: sort_list = function(items) {
        if (sort_by.key === null) {
            return items;
        } else {
            let value = sort_by.rev ? -1 : 1;
            let sorted = items.slice();
            sorted.sort(function(a, b) {
                if (a[sort_by.key] < b[sort_by.key]) {
                    return -value;
                } else if (a[sort_by.key] > b[sort_by.key]) {
                    return value;
                } else {
                    return 0;
                }
            });
            return sorted;
        }
    }

    function explain_i_index(context) {
        let have = context.value !== '1' ? 's have' : 'has';
        return `${context.value} publication${have} ${context.label} or more citation`;
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
    {#await get_publications()}
        <p>Loading publications…</p>
    {:then result}
        <h2>Metrics</h2>
        <ul>
            <li>Publication count: <strong>{result.stats.pub_count}</strong></li>
            <li>
                Average of authors per publication:
                <strong title={result.stats.avg_author_count}>{result.stats.avg_author_count.toFixed(2)}</strong>
            </li>
            <li>e-index: <strong title={result.e_index}>{result.e_index.toFixed(2)}</strong></li>
            <li>g-index: <strong>{result.g_index}</strong></li>
            <li>h-index: <strong>{result.h_index}</strong></li>
            <Chart
                dataset_label="i-index" data={result.i_indices}
                x_label='Minimum citation count'
                y_label='Publication count'
                explanation_fn={explain_i_index} />
        </ul>
        <table>
            <thead>
                <tr>
                    <th on:click={_ => set_sort(null)}>Source</th>
                    <th on:click={_ => set_sort("name")}>Title</th>
                    <th on:click={_ => set_sort("cites")}>Cited by</th>
                    <th on:click={_ => set_sort("year")}>Year</th>
                </tr>
            </thead>
            <tbody>
                {#each sort_list(result.publications) as publication}
                    <Publication {publication}/>
                {/each}
            </tbody>
        </table>
    {:catch error}
        <p>Failed to fetch dialogs: {error.message}</p>
    {/await}
</div>
