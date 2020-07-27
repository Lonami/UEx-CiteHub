<script>
    export let source;

    // TODO maybe this can be provided by the server?
    const source_info = {
        aminer: {img: "img/aminer_favicon.svg", name: "Arnet Miner"},
        academics: {img: "img/academics_favicon.svg", name: "Microsoft Academics"},
        dimensions: {img: "img/dimensions_favicon.svg", name: "Dimensions"},
        ieeexplore: {img: "img/ieeexplore_favicon.svg", name: "IEEE Xplore"},
        researchgate: {img: "img/researchgate_favicon.svg", name: "ResearchGate"},
        scholar: {img: "img/scholar_favicon.svg", name: "Google Scholar"},
    }
</script>

<style>
    img {
        width: 24px;
        height: 24px;
    }
</style>

{#if source.ref !== null}
    <a href={source.ref}>
        {#if source_info[source.key] === undefined}
            <p>{source}</p>
        {:else}
            <img src={source_info[source.key].img} title={source_info[source.key].name} alt={source_info[source.key].name}>
        {/if}
    </a>
{:else}
    <!-- We're duplicating a bit of code but it's not so much that we need another component yet. -->
    {#if source_info[source.key] === undefined}
        <p>{source}</p>
    {:else}
        <img src={source_info[source.key].img} title={source_info[source.key].name} alt={source_info[source.key].name}>
    {/if}
{/if}
