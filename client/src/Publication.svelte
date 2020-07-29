<script>
    import SourceIcon from './SourceIcon.svelte';

    export let publication;

    function title_case(string) {
        return string.replace(
            /[\w']+/g,
            function(match) {
                return match.charAt(0).toUpperCase() + match.slice(1).toLowerCase();
            }
        );
    }
</script>

<style>
    tr:nth-child(even) {
        background: #f7f7f7;
    }

    tr:nth-child(odd) {
        background: #fff;
    }

    td {
        padding: 0 16px;
    }

    .sources {
        width: 48px;
    }

    .title {
        cursor: pointer;
    }

    .title .authors, .title .publisher {
        margin: 0.3em;
        color: #666;
        font-size: small;
    }

    .cites, .year {
        text-align: center;
    }

    .help {
        border-bottom: 1px dotted #000;
        cursor: help;
    }
</style>

<tr id="publication-{publication.id}">
    <td class="sources">
        {#each publication.sources as source}
            <SourceIcon {source}/>
        {/each}
    </td>
    <td class="title">
        <p class="name">{publication.name}</p>
        <p class="authors">
            {#each publication.authors.slice(0, -1) as author}
                {title_case(author.full_name)}{", "}
            {/each}
            {#if publication.authors.length > 0}
                {title_case(publication.authors[publication.authors.length - 1].full_name)}
            {/if}
        </p>
        <!-- <p class="publisher">{publication.publisher}</p> -->
    </td>
    <td class="cites">
        {#if publication.cites === null}
            <span class="help" title="No cite count is available">?</span>
        {:else}
            {publication.cites}
        {/if}
    </td>
    <td class="year">{publication.year === null ? "No year available" : publication.year}</td>
</tr>
