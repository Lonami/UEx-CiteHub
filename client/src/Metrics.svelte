<script>
    import Publication from './Publication.svelte';
    import Chart from './Chart.svelte';

    import { get_metrics } from './rest.js';

    function explain_i_index(context) {
        let have = context.value !== '1' ? 's have' : 'has';
        return `${context.value} publication${have} ${context.label} or more citation`;
    }
</script>

{#await get_metrics()}
    <p>Loading metrics</p>
{:then result}
    {#if result.pub_count == 0}
        <p>
            No publications have been fetched yet. <a href="/profile">Fill your profile</a> with
            all of the relevant sources you own to start retrieving data from those sites, and
            after a while refresh this page to get the results.
        </p>
    {/if}
    <ul>
        <li>Publication count: <strong>{result.pub_count}</strong></li>
        <li>
            Average of authors per publication:
            <strong title={result.avg_author_count}>{result.avg_author_count.toFixed(2)}</strong>
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
{:catch error}
    <p>Failed to fetch metrics: {error.message}</p>
{/await}
