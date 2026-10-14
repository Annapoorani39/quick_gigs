(function () {
    const byId = (id) => document.getElementById(id);
    const csrfToken = () => {
        const field = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return field ? field.value : "";
    };

    function normalizeSkill(skill) {
        return String(skill || "").toLocaleLowerCase()
            .replace(/[^a-z0-9\s]/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    async function readJson(response) {
        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error("The server returned an unreadable response. Please try again.");
        }
        if (!response.ok) {
            throw new Error(data.error || "The request could not be completed.");
        }
        return data;
    }

    function splitSkills(text) {
        const seen = new Set();
        return String(text || "").split(/[,;\n]+/).map((skill) => skill.trim())
            .filter((skill) => {
                const key = normalizeSkill(skill);
                if (!key || seen.has(key)) return false;
                seen.add(key);
                return true;
            });
    }

    function createElement(tag, text) {
        const element = document.createElement(tag);
        element.textContent = text;
        return element;
    }

    async function saveProfileSkills(skills) {
        const response = await fetch("/api/profile/skills/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ skills }),
        });
        return readJson(response);
    }

    function initSingleSubmitForms() {
        document.querySelectorAll("form [data-submit-once]").forEach((button) => {
            const form = button.form;
            if (!form) return;
            form.addEventListener("submit", () => {
                if (!form.checkValidity()) return;
                button.disabled = true;
                button.textContent = "Submitting…";
            });
        });
    }

    function initVoiceInput() {
        const startButtons = document.querySelectorAll("[data-voice-target]");
        if (!startButtons.length) return;

        const status = byId("voice-status");
        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = null;
        let target = null;
        let activeButton = null;

        if (!Recognition) {
            if (status) status.textContent = "Speech recognition is not available in this browser. Type in the field instead.";
            startButtons.forEach((button) => {
                button.addEventListener("click", () => {
                    if (status) status.textContent = "Speech recognition is unavailable. You can enter and edit the text manually.";
                });
            });
            return;
        }

        recognition = new Recognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.onstart = () => {
            if (status) status.textContent = "Listening. Speak clearly; you can edit the recognized text afterward.";
        };
        recognition.onresult = (event) => {
            if (!target) return;
            const transcript = Array.from(event.results)
                .map((result) => result[0].transcript)
                .join(" ")
                .trim();
            target.value = transcript;
            target.dispatchEvent(new Event("input", { bubbles: true }));
        };
        recognition.onerror = (event) => {
            const messages = {
                "not-allowed": "Microphone permission was denied. Allow microphone access in the browser or type your details.",
                "service-not-allowed": "The browser speech service is blocked. Type your details instead.",
                "no-speech": "No speech was detected. Try again or type your details.",
                "audio-capture": "No microphone was found. Connect a microphone or type your details.",
                network: "Speech recognition could not reach the browser speech service. Check your connection or type your details.",
            };
            if (status) status.textContent = messages[event.error] || `Speech recognition error (${event.error}). You can type your details.`;
        };
        recognition.onend = () => {
            if (activeButton) activeButton.disabled = false;
            activeButton = null;
            if (status && status.textContent.startsWith("Listening.")) {
                status.textContent = "Listening ended. Review and edit the recognized text before saving.";
            }
        };

        startButtons.forEach((button) => button.addEventListener("click", () => {
            target = byId(button.dataset.voiceTarget);
            if (!target) {
                if (status) status.textContent = "The input field for voice recognition could not be found.";
                return;
            }
            const language = byId("voice-language") || byId("profile-voice-language");
            recognition.lang = language ? language.value : "en-IN";
            activeButton = button;
            button.disabled = true;
            try {
                recognition.start();
            } catch (error) {
                button.disabled = false;
                activeButton = null;
                if (status) status.textContent = "Speech recognition is already running. Stop it before starting again.";
            }
        }));

        document.querySelectorAll("[data-voice-stop]").forEach((button) => {
            button.addEventListener("click", () => {
                if (!activeButton) {
                    if (status) status.textContent = "Speech recognition is not currently running.";
                    return;
                }
                recognition.stop();
            });
        });
    }

    function initResumeBuilder() {
        const form = byId("resume-form");
        if (!form) return;

        const skillsField = byId("resume-skills");
        const tags = byId("skill-tags");
        const preview = byId("resume-preview");
        const status = byId("resume-status");

        function refreshTags() {
            tags.replaceChildren();
            splitSkills(skillsField.value).forEach((skill) => {
                const chip = document.createElement("span");
                chip.className = "skill-tag";
                chip.append(document.createTextNode(`${skill} `));
                const remove = createElement("button", "Remove");
                remove.type = "button";
                remove.setAttribute("aria-label", `Remove ${skill}`);
                remove.addEventListener("click", () => {
                    skillsField.value = splitSkills(skillsField.value)
                        .filter((item) => item.toLocaleLowerCase() !== skill.toLocaleLowerCase()).join(", ");
                    refreshTags();
                });
                chip.append(remove);
                tags.append(chip);
            });
        }

        function payloadFromForm() {
            return {
                full_name: byId("resume-name").value.trim(),
                email: byId("resume-email").value.trim(),
                phone: byId("resume-phone").value.trim(),
                location: byId("resume-location").value.trim(),
                target_job: byId("target-job").value.trim(),
                objective: byId("resume-objective").value.trim(),
                education: byId("resume-education").value.trim(),
                skills: splitSkills(skillsField.value),
                projects: byId("resume-projects").value.trim(),
                experience: byId("resume-experience").value.trim(),
                experience_text: byId("resume-experience").value.trim(),
                certifications: byId("resume-certifications").value.trim(),
                languages: byId("resume-languages").value.trim(),
            };
        }

        function renderResume(resume) {
            preview.replaceChildren();
            preview.append(createElement("h3", resume.full_name || "Resume"));
            const contact = [resume.email, resume.phone, resume.location].filter(Boolean).join(" · ");
            if (contact) preview.append(createElement("p", contact));
            if (resume.target_job) preview.append(createElement("p", `Target job: ${resume.target_job}`));
            const sections = [
                ["Career objective", resume.professional_summary],
                ["Education", resume.education],
                ["Skills", (resume.skills || []).join(", ")],
                ["Projects", resume.projects],
                ["Experience", resume.experience],
                ["Certifications", resume.certifications],
                ["Languages", resume.languages],
            ];
            sections.forEach(([heading, value]) => {
                if (!value) return;
                preview.append(createElement("h4", heading));
                preview.append(createElement("p", value));
            });
            if (!sections.some((section) => section[1])) {
                preview.append(createElement("p", "Add details in the form to complete your resume."));
            }
        }

        skillsField.addEventListener("input", refreshTags);
        byId("add-skill").addEventListener("click", () => {
            const field = byId("new-skill");
            const skill = field.value.trim();
            if (!skill) {
                field.focus();
                return;
            }
            const current = splitSkills(skillsField.value);
            if (!current.some((item) => item.toLocaleLowerCase() === skill.toLocaleLowerCase())) {
                current.push(skill);
                skillsField.value = current.join(", ");
                refreshTags();
            }
            field.value = "";
            field.focus();
        });

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            status.textContent = "Generating your resume preview…";
            try {
                const response = await fetch("/api/resumes/generate/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                    body: JSON.stringify(payloadFromForm()),
                });
                const data = await readJson(response);
                renderResume(data.resume);
                status.textContent = "Preview generated from the information you provided.";
            } catch (error) {
                status.textContent = error.message;
            }
        });

        byId("download-pdf").addEventListener("click", async () => {
            const payload = payloadFromForm();
            if (!payload.full_name && !payload.objective && !payload.education && !payload.experience && !payload.skills.length) {
                status.textContent = "Add at least one resume detail before downloading.";
                return;
            }
            status.textContent = "Preparing your PDF…";
            try {
                const printableText = Object.values(payload).flat().join(" ");
                if (/[^\u0000-\u00ff]/.test(printableText)) {
                    const previewResponse = await fetch("/api/resumes/generate/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                        body: JSON.stringify(payload),
                    });
                    const previewData = await readJson(previewResponse);
                    renderResume(previewData.resume);
                    status.textContent = "Use your browser's print dialog and choose Save as PDF to preserve Tamil and other Unicode text.";
                    window.print();
                    return;
                }
                const response = await fetch("/api/resumes/pdf/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    const data = await readJson(response);
                    throw new Error(data.error || "The PDF could not be created.");
                }
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "skillmatch-resume.pdf";
                document.body.append(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(url);
                status.textContent = "Your PDF download has started.";
            } catch (error) {
                status.textContent = error.message;
            }
        });

        byId("extract-resume").addEventListener("click", async () => {
            const file = byId("resume-upload").files[0];
            const uploadStatus = byId("upload-status");
            if (!file) {
                uploadStatus.textContent = "Choose a PDF or DOCX file first.";
                return;
            }
            const body = new FormData();
            body.append("resume", file);
            body.append("csrfmiddlewaretoken", csrfToken());
            uploadStatus.textContent = "Reading the resume. The uploaded file is processed for this request and not stored.";
            try {
                const response = await fetch("/api/resumes/extract/", {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken() },
                    body,
                });
                const data = await readJson(response);
                skillsField.value = (data.skills || []).join(", ");
                const sections = data.sections || {};
                if (sections.education) byId("resume-education").value = sections.education;
                if (sections.projects) byId("resume-projects").value = sections.projects;
                if (sections.experience) byId("resume-experience").value = sections.experience;
                if (sections.certifications) byId("resume-certifications").value = sections.certifications;
                if (sections.languages) byId("resume-languages").value = sections.languages;
                refreshTags();
                const extracted = byId("extracted-sections");
                extracted.replaceChildren();
                extracted.append(createElement("p", `Detected skills: ${(data.skills || []).join(", ") || "none from the supported skill list"}. Review and edit before use.`));
                if (!Object.keys(sections).length) {
                    extracted.append(createElement("p", "No labeled education, projects, experience, certification, or language sections were recognized. Review the original resume and enter these fields manually."));
                }
                uploadStatus.textContent = `${data.source}. The file was not stored.`;
            } catch (error) {
                uploadStatus.textContent = `${error.message} You can enter the resume details manually.`;
            }
        });

        const saveSkillsButton = byId("save-resume-skills");
        if (saveSkillsButton) {
            saveSkillsButton.addEventListener("click", async () => {
                if (saveSkillsButton.disabled) {
                    status.textContent = "Sign in before saving skills to your profile.";
                    return;
                }
                saveSkillsButton.disabled = true;
                status.textContent = "Saving your reviewed skills…";
                try {
                    const data = await saveProfileSkills(splitSkills(skillsField.value));
                    skillsField.value = data.skills.join(", ");
                    refreshTags();
                    status.textContent = "Your reviewed skills were saved to your profile.";
                } catch (error) {
                    status.textContent = error.message;
                } finally {
                    saveSkillsButton.disabled = false;
                }
            });
        }

        refreshTags();
    }

    function initJobMatches() {
        const skillsField = byId("candidate-skills");
        if (!skillsField) return;
        let learningResources = {};
        const resourcesJson = byId("learning-resources-data");
        if (resourcesJson) {
            try {
                learningResources = JSON.parse(resourcesJson.textContent);
            } catch (error) {
                learningResources = {};
            }
        }

        const cards = Array.from(document.querySelectorAll("[data-match-card]"));
        const refreshCards = [];
        cards.forEach((card) => {
            const required = (card.dataset.required || "").split("||").map((skill) => skill.trim()).filter(Boolean);
            const score = card.querySelector("[data-score]");
            const explanation = card.querySelector("[data-explanation]");
            const matchedList = card.querySelector("[data-matched]");
            const missingList = card.querySelector("[data-missing]");
            const progress = card.querySelector("[data-progress]");
            const progressLabel = card.querySelector("[data-progress-label]");
            const progressOptions = card.querySelector("[data-progress-options]");
            const resourcesBlock = card.querySelector("[data-learning-resources]");
            const resourcesDetails = card.querySelector("[data-resources-details]");
            const completedData = byId("completed-skill-keys-data");
            let completedSkillKeys = [];
            if (completedData) {
                try {
                    completedSkillKeys = JSON.parse(completedData.textContent);
                } catch (error) {
                    completedSkillKeys = [];
                }
            }
            const completed = new Set(completedSkillKeys.map(normalizeSkill));
            const progressStatus = card.querySelector("[data-progress-status]");
            const canSaveProgress = document.body.dataset.canSaveProgress === "true";

            function drawList(list, values, emptyText) {
                list.replaceChildren();
                if (!values.length) {
                    list.append(createElement("li", emptyText));
                    return;
                }
                values.forEach((value) => list.append(createElement("li", value)));
            }

            function refreshProgress(missing) {
                progressOptions.replaceChildren();
                updateProgressLabel(missing);
                missing.forEach((skill) => {
                    const label = document.createElement("label");
                    const checkbox = document.createElement("input");
                    checkbox.type = "checkbox";
                    checkbox.checked = completed.has(normalizeSkill(skill));
                    checkbox.disabled = !canSaveProgress;
                    checkbox.addEventListener("change", async () => {
                        const skillKey = normalizeSkill(skill);
                        const wasCompleted = completed.has(skillKey);
                        if (checkbox.checked) completed.add(skillKey);
                        else completed.delete(skillKey);
                        updateProgressLabel(missing);
                        checkbox.disabled = true;
                        try {
                            const response = await fetch("/api/learning/progress/", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                                body: JSON.stringify({ skill, completed: checkbox.checked }),
                            });
                            await readJson(response);
                            progressStatus.textContent = "Learning progress saved.";
                        } catch (error) {
                            if (wasCompleted) completed.add(skillKey);
                            else completed.delete(skillKey);
                            checkbox.checked = wasCompleted;
                            updateProgressLabel(missing);
                            progressStatus.textContent = error.message;
                        } finally {
                            checkbox.disabled = !canSaveProgress;
                        }
                    });
                    label.append(checkbox, document.createTextNode(` ${skill}`));
                    progressOptions.append(label);
                });
            }

            function updateProgressLabel(missing) {
                const currentCompleted = missing.filter((skill) => completed.has(normalizeSkill(skill))).length;
                progress.max = Math.max(1, missing.length);
                progress.value = currentCompleted;
                const percentage = missing.length ? Math.round(currentCompleted / missing.length * 100) : 0;
                progressLabel.textContent = `${currentCompleted} of ${missing.length} missing skills marked complete (${percentage}%)`;
            }

            function refresh() {
                if (!required.length) {
                    score.textContent = "—";
                    explanation.textContent = "No listed skill requirements; a match percentage cannot be calculated.";
                    drawList(matchedList, [], "No requirements listed.");
                    drawList(missingList, [], "No requirements listed.");
                    refreshProgress([]);
                    if (resourcesBlock) resourcesBlock.replaceChildren();
                    if (resourcesDetails) resourcesDetails.hidden = true;
                    return;
                }
                const candidates = new Set(splitSkills(skillsField.value).map(normalizeSkill));
                const matched = required.filter((skill) => candidates.has(normalizeSkill(skill)));
                const missing = required.filter((skill) => !candidates.has(normalizeSkill(skill)));
                const percentage = Math.round((matched.length / required.length) * 100);
                score.textContent = `${percentage}%`;
                explanation.textContent = `${matched.length} of ${required.length} listed required skills match (matched required skills ÷ total listed required skills × 100).`;
                drawList(matchedList, matched, "No listed skills matched yet.");
                drawList(missingList, missing, "No skill gaps in the listed requirements.");
                refreshProgress(missing);
                if (resourcesBlock) {
                    resourcesBlock.replaceChildren();
                    missing.forEach((skill) => {
                        const links = learningResources[normalizeSkill(skill)] ||
                            [`https://www.youtube.com/results?search_query=${encodeURIComponent(`${skill} training`)}`];
                        const row = document.createElement("li");
                        row.append(document.createTextNode(`${skill}: `));
                        links.forEach((href, index) => {
                            if (index) row.append(document.createTextNode(" · "));
                            const link = createElement("a", `Learning resource ${index + 1}`);
                            link.href = href;
                            link.target = "_blank";
                            link.rel = "noopener noreferrer";
                            row.append(link);
                        });
                        resourcesBlock.append(row);
                    });
                }
                if (resourcesDetails) resourcesDetails.hidden = missing.length === 0;
            }

            refreshCards.push(refresh);
        });

        const simulateButton = byId("simulate-match");
        const simulateSkill = byId("simulate-skill");
        const simulationStatus = byId("simulation-status");
        function refreshAllMatches() {
            refreshCards.forEach((refresh) => refresh());
            const candidates = new Set(splitSkills(skillsField.value).map(normalizeSkill));
            const visibleMatches = [];
            cards.forEach((card) => {
                const required = (card.dataset.required || "").split("||").map((skill) => skill.trim()).filter(Boolean);
                const matched = required.filter((skill) => candidates.has(normalizeSkill(skill)));
                const score = required.length ? Math.round(matched.length / required.length * 100) : null;
                card.dataset.score = score === null ? "" : String(score);
                if (score !== null) visibleMatches.push(score);
            });
            const bestScore = visibleMatches.length ? Math.max(...visibleMatches) : null;
            const bestSummary = byId("summary-best");
            if (bestSummary) bestSummary.textContent = bestScore === null ? "—" : `${bestScore}%`;
            const matchedSummary = byId("summary-matched");
            if (matchedSummary) {
                const uniqueMatched = new Set();
                cards.forEach((card) => {
                    const required = (card.dataset.required || "").split("||").map((skill) => skill.trim()).filter(Boolean);
                    required.filter((skill) => candidates.has(normalizeSkill(skill))).forEach((skill) => uniqueMatched.add(normalizeSkill(skill)));
                });
                matchedSummary.textContent = String(uniqueMatched.size);
            }
            const missingSummary = byId("summary-missing");
            if (missingSummary) {
                const uniqueMissing = new Set();
                cards.forEach((card) => {
                    const required = (card.dataset.required || "").split("||").map((skill) => skill.trim()).filter(Boolean);
                    required.filter((skill) => !candidates.has(normalizeSkill(skill))).forEach((skill) => uniqueMissing.add(normalizeSkill(skill)));
                });
                missingSummary.textContent = String(uniqueMissing.size);
            }
            if (!simulateSkill) return;

            const previouslySelected = normalizeSkill(simulateSkill.value);
            const availableSkills = new Map();
            cards.forEach((card) => {
                const required = (card.dataset.required || "").split("||").map((skill) => skill.trim()).filter(Boolean);
                required.forEach((skill) => {
                    const key = normalizeSkill(skill);
                    if (key && !candidates.has(key) && !availableSkills.has(key)) {
                        availableSkills.set(key, skill);
                    }
                });
            });

            simulateSkill.replaceChildren(createElement("option", "Choose a skill"));
            availableSkills.forEach((skill) => {
                const option = document.createElement("option");
                option.value = skill;
                option.textContent = skill;
                simulateSkill.append(option);
            });
            if (availableSkills.has(previouslySelected)) {
                simulateSkill.value = availableSkills.get(previouslySelected);
            }
        }
        skillsField.addEventListener("input", refreshAllMatches);
        refreshAllMatches();

        const jobList = byId("match-job-list");
        const searchField = byId("match-search");
        const minScore = byId("minimum-match");
        const locationField = byId("match-location");
        const jobTypeField = byId("match-job-type");
        const sortField = byId("match-sort");
        const noFilteredResults = byId("no-filtered-matches");
        const matchStatus = byId("match-status");

        function applyFilters() {
            if (!jobList) return;
            const search = (searchField?.value || "").trim().toLocaleLowerCase();
            const location = (locationField?.value || "").trim().toLocaleLowerCase();
            const minimum = Number(minScore?.value || 0);
            const jobType = (jobTypeField?.value || "").toLocaleLowerCase();
            const sort = sortField?.value || "score";
            const visible = [];
            cards.forEach((card) => {
                const scoreValue = card.dataset.score;
                const haystack = [
                    card.dataset.title, card.dataset.company, card.dataset.location,
                    card.dataset.description, card.dataset.required,
                ].join(" ").toLocaleLowerCase();
                const meetsScore = scoreValue !== "" && scoreValue !== undefined && Number(scoreValue) >= minimum;
                const matches = (!search || haystack.includes(search))
                    && (!location || (card.dataset.location || "").toLocaleLowerCase().includes(location))
                    && (!jobType || (card.dataset.jobType || "").toLocaleLowerCase() === jobType)
                    && (minimum === 0 ? scoreValue === "" || meetsScore : meetsScore);
                card.hidden = !matches;
                if (matches) visible.push(card);
            });
            visible.sort((left, right) => {
                if (sort === "title") return (left.dataset.title || "").localeCompare(right.dataset.title || "");
                if (sort === "newest") return Number(right.dataset.created || 0) - Number(left.dataset.created || 0);
                const leftScore = left.dataset.score === "" ? -1 : Number(left.dataset.score);
                const rightScore = right.dataset.score === "" ? -1 : Number(right.dataset.score);
                return rightScore - leftScore || Number(right.dataset.created || 0) - Number(left.dataset.created || 0);
            }).forEach((card) => jobList.append(card));
            if (noFilteredResults) noFilteredResults.hidden = visible.length > 0 || cards.length === 0;
            if (matchStatus) matchStatus.textContent = `${visible.length} of ${cards.length} jobs shown.`;
        }
        [searchField, minScore, locationField, jobTypeField, sortField].forEach((control) => {
            control?.addEventListener(control.tagName === "INPUT" ? "input" : "change", applyFilters);
        });
        byId("clear-match-filters")?.addEventListener("click", () => {
            if (searchField) searchField.value = "";
            if (minScore) minScore.value = "0";
            if (locationField) locationField.value = "";
            if (jobTypeField) jobTypeField.value = "";
            if (sortField) sortField.value = "score";
            applyFilters();
        });
        byId("refresh-matches")?.addEventListener("click", async (event) => {
            const button = event.currentTarget;
            if (button.disabled) return;
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "Refreshing…";
            if (matchStatus) matchStatus.textContent = "Loading current published jobs and recalculating matches…";
            try {
                const params = new URLSearchParams({ skills: splitSkills(skillsField.value).join(", ") });
                await readJson(await fetch(`/api/jobs/recommendations/?${params.toString()}`));
                const pageParams = new URLSearchParams(window.location.search);
                pageParams.set("skills", splitSkills(skillsField.value).join(", "));
                window.location.assign(`${window.location.pathname}?${pageParams.toString()}`);
            } catch (error) {
                if (matchStatus) matchStatus.textContent = `Could not refresh matches: ${error.message}`;
                button.disabled = false;
                button.textContent = originalText;
            }
        });
        skillsField.addEventListener("input", applyFilters);
        applyFilters();

        if (simulateButton && simulateSkill && simulationStatus) {
            simulateButton.addEventListener("click", async () => {
                if (!simulateSkill.value) {
                    simulationStatus.textContent = "Choose one missing skill from a listed job to simulate.";
                    simulateSkill.focus();
                    return;
                }
                simulateButton.disabled = true;
                simulationStatus.textContent = "Calculating against current published jobs…";
                try {
                    const response = await fetch("/api/matching/simulate/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                        body: JSON.stringify({
                            user_skills: splitSkills(skillsField.value),
                            selected_skill: simulateSkill.value,
                        }),
                    });
                    const data = await readJson(response);
                    const result = data.simulation;
                    simulationStatus.textContent = result.jobs_count
                        ? `Across ${result.jobs_count} published job${result.jobs_count === 1 ? "" : "s"} with listed skills, the best match changes from ${result.before}% to ${result.after}% (+${result.improvement} percentage points). This is a projection only and does not save your profile.`
                        : "No current published jobs have listed skills, so a match projection cannot be calculated.";
                } catch (error) {
                    simulationStatus.textContent = error.message;
                } finally {
                    simulateButton.disabled = false;
                }
            });
        }
    }

    function initSkillStimulator() {
        const jobSelect = byId("stimulator-job");
        if (jobSelect) {
            jobSelect.addEventListener("change", () => {
                const url = new URL(window.location.href);
                if (jobSelect.value) url.searchParams.set("job_id", jobSelect.value);
                else url.searchParams.delete("job_id");
                window.location.assign(url.toString());
            });
        }

        const status = byId("stimulator-status");
        const completedData = byId("stimulator-completed-skills");
        let completedSkills = [];
        if (completedData) {
            try {
                completedSkills = JSON.parse(completedData.textContent).map(normalizeSkill);
            } catch (error) {
                completedSkills = [];
            }
        }
        const stimulatorProgress = byId("stimulator-overall-progress");
        const stimulatorProgressLabel = byId("stimulator-progress-label");
        function updateStimulatorProgress() {
            if (!stimulatorProgress || !stimulatorProgressLabel) return;
            const checkboxes = Array.from(document.querySelectorAll("[data-progress-skill]"));
            const completed = checkboxes.filter((checkbox) => checkbox.checked).length;
            stimulatorProgress.max = Math.max(1, checkboxes.length);
            stimulatorProgress.value = completed;
            stimulatorProgressLabel.textContent = `${completed} of ${checkboxes.length} missing skills marked complete.`;
        }
        updateStimulatorProgress();
        document.querySelectorAll("[data-progress-skill]").forEach((checkbox) => {
            checkbox.checked = completedSkills.includes(normalizeSkill(checkbox.dataset.progressSkill));
            checkbox.addEventListener("change", async () => {
                if (checkbox.disabled) return;
                const wasCompleted = !checkbox.checked;
                checkbox.disabled = true;
                if (status) status.textContent = "Saving learning progress…";
                try {
                    await readJson(await fetch("/api/learning/progress/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                        body: JSON.stringify({ skill: checkbox.dataset.progressSkill, completed: checkbox.checked }),
                    }));
                    updateStimulatorProgress();
                    const label = checkbox.closest("label");
                    if (label) label.dataset.saved = String(checkbox.checked);
                    if (status) status.textContent = "Learning progress saved to your account.";
                } catch (error) {
                    checkbox.checked = wasCompleted;
                    updateStimulatorProgress();
                    if (status) status.textContent = error.message;
                } finally {
                    checkbox.disabled = false;
                }
            });
        });
    }

    function initExperienceCapture() {
        const button = byId("analyze-speech");
        if (!button) return;
        const status = byId("analysis-status");
        const skillField = byId("extracted-skills");
        const transcript = byId("speech-output");
        button.addEventListener("click", async () => {
            const text = transcript.value.trim();
            if (!text) {
                status.textContent = "Enter or record your work experience before extracting skills.";
                transcript.focus();
                return;
            }
            status.textContent = "Extracting skills from your text…";
            try {
                const response = await fetch("/api/skills/extract/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
                    body: JSON.stringify({ text }),
                });
                const data = await readJson(response);
                skillField.value = (data.skills || []).join(", ");
                status.textContent = data.skills && data.skills.length
                    ? "Review and edit the skills before saving. No unlisted skills were inferred."
                    : "No supported skills were detected. You can enter skills manually.";
            } catch (error) {
                status.textContent = error.message;
            }
        });

        const saveButton = byId("save-extracted-skills");
        if (saveButton) {
            saveButton.addEventListener("click", async () => {
                if (saveButton.disabled) {
                    status.textContent = "Sign in before saving skills to a profile.";
                    return;
                }
                status.textContent = "Saving your reviewed skills…";
                try {
                    const data = await saveProfileSkills(splitSkills(skillField.value));
                    skillField.value = data.skills.join(", ");
                    status.textContent = "Your reviewed skills were saved to your profile.";
                } catch (error) {
                    status.textContent = error.message;
                }
            });
        }
    }

    initVoiceInput();
    initSingleSubmitForms();
    initResumeBuilder();
    initJobMatches();
    initSkillStimulator();
    initExperienceCapture();
})();
