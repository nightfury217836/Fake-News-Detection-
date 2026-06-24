document.addEventListener("DOMContentLoaded", () => {

    // SELECTORS
    const searchInput = document.getElementById("search");
    const searchBtn = document.getElementById("searchBtn");
    const countrySelect = document.getElementById("country");
    const categorySelect = document.getElementById("category");
    const newsContainer = document.getElementById("news-container");
    const loadingState = document.getElementById("loading-state");
    const emptyState = document.getElementById("empty-state");
    const biasSection = document.getElementById("bias-section");
    const biasContainer = document.getElementById("bias-container");


    // EVENT LISTENERS
    searchBtn.addEventListener("click", loadNews);

    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") loadNews();
    });


    // SCOPED FUNCTIONS (Removed window. for better practice)
    window.quickSearch = (keyword) => {
        searchInput.value = keyword;
        loadNews();
    };


    async function loadNews() {

        const country = countrySelect?.value || "";
        const category = categorySelect?.value || "";
        const search = searchInput.value.trim();

        newsContainer.innerHTML = "";
        biasSection.classList.add("hidden");
        emptyState.classList.add("hidden");
        loadingState.classList.remove("hidden");
        searchBtn.disabled = true;

        try {

            let url = `/api/top-news?`;

            if (search !== "") {
                url += `q=${encodeURIComponent(search)}`;
            } else {
                url += `country=${country}&category=${category}`;
            }

            const res = await fetch(url);

            if (!res.ok) {
                throw new Error("Network response failed");
            }

            const data = await res.json();
            const articles = data.articles || [];

            loadingState.classList.add("hidden");
            searchBtn.disabled = false;

            if (articles.length === 0) {
                emptyState.textContent = "No news found for your search.";
                emptyState.classList.remove("hidden");
                return;
            }

            renderMainArticle(articles[0]);
            articles.slice(1).forEach(renderSubArticle);

        } catch (error) {

            loadingState.classList.add("hidden");
            searchBtn.disabled = false;
            emptyState.textContent = "Error fetching news. Try again.";
            emptyState.classList.remove("hidden");

            console.error("Fetch Error:", error);
        }
    }


    function renderMainArticle(article) {

        const card = document.createElement("div");
        card.className = "news-subcard main-card";

        // Using Template Literal for structure
        card.innerHTML = `
            <h2>${article.title}</h2>
            <p>${article.summary || "Summary unavailable."}</p>
            <p>
                <strong>Sentiment:</strong> 
                ${article.sentiment?.label || "N/A"} 
                (${Math.round((article.sentiment?.score || 0) * 100)}%)
            </p>
            <p>
                <strong>Source:</strong> ${article.source || "Unknown"}
            </p>
            <a href="${article.url}" target="_blank">Read Full Article</a>
        `;

        const checkBtn = document.createElement("button");
        checkBtn.textContent = "Check Perspectives";
        checkBtn.className = "perspective-btn"; // Good for CSS
        checkBtn.onclick = () => checkNews(article.title); // Simpler binding

        card.appendChild(checkBtn);
        newsContainer.appendChild(card);
    }


    function renderSubArticle(article) {

        const card = document.createElement("div");
        card.className = "news-subcard";

        card.innerHTML = `
            <h3>${article.title}</h3>
            <p>${article.summary || ""}</p>
            <p>
                <strong>Sentiment:</strong> 
                ${article.sentiment?.label || "N/A"} 
                (${Math.round((article.sentiment?.score || 0) * 100)}%)
            </p>
            <a href="${article.url}" target="_blank">Read More</a>
        `;

        newsContainer.appendChild(card);
    }


    async function checkNews(title) {

    biasContainer.innerHTML = "<p>Fetching perspectives...</p>";
    biasSection.classList.remove("hidden");
    biasSection.scrollIntoView({ behavior: "smooth" });

    try {

        const res = await fetch(`/api/check-news?title=${encodeURIComponent(title)}`);
        const data = await res.json();

        biasContainer.innerHTML = "";

        /* ---------------------------
           Calculate Bias Position
        --------------------------- */

        let scores = [];

        ["left","center","right"].forEach(side=>{
            const arr = data.bias?.[side] || [];
            arr.forEach(a=>{
                if(a.bias_score !== undefined){
                    scores.push(a.bias_score);
                }
            });
        });

        let avgBias = 50;
        if(scores.length){
            avgBias = scores.reduce((a,b)=>a+b)/scores.length;
        }

        /* ---------------------------
           Bias Visual Slider
        --------------------------- */

        const visual = document.createElement("div");
        visual.className = "bias-visual";

        visual.innerHTML = `
            <div class="bias-scale">
                <div class="bias-marker" style="left:${avgBias}%"></div>
            </div>

            <div class="bias-labels">
                <span>LEFT</span>
                <span>CENTER</span>
                <span>RIGHT</span>
            </div>
        `;

        biasContainer.appendChild(visual);

        /* ---------------------------
           Bias Articles Grid
        --------------------------- */

        const grid = document.createElement("div");
        grid.className = "bias-grid";

        ["left","center","right"].forEach(side=>{

            const col = document.createElement("div");
            col.className = `bias-column bias-${side}`;

            const heading = document.createElement("h4");
            heading.textContent = side.toUpperCase();

            col.appendChild(heading);

            const sideData = data.bias?.[side];

            if(sideData && sideData.length){

                sideData.forEach(article=>{

                    const item = document.createElement("div");
                    item.className = "bias-item";

                    item.innerHTML = `
                        <a href="${article.url}" target="_blank">
                            ${article.title}
                        </a>
                        <div class="score">
                            Bias Score: ${article.bias_score}
                        </div>
                    `;

                    col.appendChild(item);

                });

            }else{

                const empty = document.createElement("p");
                empty.textContent = "No sources";
                empty.style.fontSize = "11px";
                col.appendChild(empty);

            }

            grid.appendChild(col);

        });

        biasContainer.appendChild(grid);

    } catch(err){

        biasContainer.innerHTML = "<p>Error fetching perspectives</p>";
        console.error(err);

    }
}


    function renderTrendingTags(tags) {

        const trendingContainer = document.querySelector(".trending-tags");

        if (!trendingContainer) return;

        trendingContainer.innerHTML = "";

        tags.forEach(tag => {

            const btn = document.createElement("button");

            btn.textContent = `#${tag}`;

            btn.addEventListener("click", () => quickSearch(tag));

            trendingContainer.appendChild(btn);
        });
    }

});