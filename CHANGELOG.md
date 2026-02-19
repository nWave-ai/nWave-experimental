# CHANGELOG

<!-- version list -->

## v2.17.2 (2026-02-19)

### Bug Fixes

- **docs**: Add missing argument-hint to forge and research commands
  ([`86e43b1`](https://github.com/nWave-ai/nwave-dev/commit/86e43b1a0d40ffa4f5eea1f7bc313c1b2ccad679))

- **release**: Exclude dev-only artifacts from public repo sync
  ([`d0de876`](https://github.com/nWave-ai/nwave-dev/commit/d0de8768dd9d90e6470c30d54957ccb92b9620b0))

- **release**: Stop semantic-release from regenerating CHANGELOG.md
  ([`79925ec`](https://github.com/nWave-ai/nwave-dev/commit/79925ecca39cb9c8aa5942072771578c4d3e77ae))

### Features

- **docs**: Add deterministic documentation generator (nwave-docgen)
  ([`c5b8417`](https://github.com/nWave-ai/nwave-dev/commit/c5b841738705291548a281a32dbadb79269f55be))

- **docs**: Add wave grouping, command↔agent cross-refs, and skill links
  ([`4d6b610`](https://github.com/nWave-ai/nwave-dev/commit/4d6b61064629ad5054bebc1b74931abda7b0cfe4))

- **docs**: Add wave grouping, cross-refs, skill links, and fix front-matter
  ([`82f62db`](https://github.com/nWave-ai/nwave-dev/commit/82f62dbc6d73fd809f77dc50d6f4c6cc2188269c))

- **nwave**: Standardize skill descriptions, add Radical Candor reviews, and quality-driven design
  ([`b37b999`](https://github.com/nWave-ai/nwave-dev/commit/b37b999d17cc72097a7b9c5cbad7ad3374e5e4c3))


## v2.17.1 (2026-02-18)

### Bug Fixes

- **release**: Add git identity for nwave-dev marker tag
  ([`3705b54`](https://github.com/nWave-ai/nwave-dev/commit/3705b54832aee375f10161017d2385d47598c61d))


## v2.17.0 (2026-02-18)

### Features

- **release**: Dynamic changelog from nwave-dev commits + pipeline cleanup
  ([`7056154`](https://github.com/nWave-ai/nwave-dev/commit/7056154daab6b2890d4399395bf2e2588a9cb725))


## v2.16.5 (2026-02-17)

### Bug Fixes

- **des**: Enforce commit after GREEN and increase max_turns defaults
  ([`b4bb8f3`](https://github.com/nWave-ai/nwave-dev/commit/b4bb8f3f0ce616e8340e90209afd2aae79bc529b))


## v2.16.4 (2026-02-17)

### Bug Fixes

- **nw**: Deliver Phase 3 must explicitly invoke /nw:refactor
  ([`c9b2e12`](https://github.com/nWave-ai/nwave-dev/commit/c9b2e12114151f33ac776c3ee6e264f3289a077e))


## v2.16.3 (2026-02-16)

### Bug Fixes

- **des**: Remove unsupported systemMessage from hook response
  ([`ec713a5`](https://github.com/nWave-ai/nwave-dev/commit/ec713a51b27f99a0871c6bf88029385661e9426e))


## v2.16.2 (2026-02-16)

### Bug Fixes

- **des**: Remove unrecognized hookSpecificOutput from SubagentStop block response
  ([`207b7d3`](https://github.com/nWave-ai/nwave-dev/commit/207b7d307185c455f270deb44fe68ff3a298763d))


## v2.16.1 (2026-02-15)


## v2.16.0 (2026-02-15)

### Bug Fixes

- **des**: Use installer Python for hooks, remove pipenv prerequisite
  ([`ae1fb21`](https://github.com/nWave-ai/nwave-dev/commit/ae1fb2193611d615469fcf00c91d5b19f91edd73))

- **tests**: Accept any Python path in hook format assertion
  ([`95ef8c9`](https://github.com/nWave-ai/nwave-dev/commit/95ef8c9bf4fc6624140e1320b186fa5f2c6be192))


## v2.15.2 (2026-02-14)


## v2.15.1 (2026-02-13)


## v2.15.0 (2026-02-13)

### Features

- **deliver**: Enforce step-id format and clarify DES validation rules
  ([`26dbb82`](https://github.com/nWave-ai/nwave-dev/commit/26dbb82d8c6f3ea043d8159e7159d7f51bcb7708))


## v2.14.16 (2026-02-13)


## v2.14.15 (2026-02-13)


## v2.14.14 (2026-02-13)


## v2.14.13 (2026-02-13)

### Bug Fixes

- **release**: Replace dual README with single-source + link rewriting
  ([`a087033`](https://github.com/nWave-ai/nwave-dev/commit/a0870336c282323d83b42b08f6a164f9f257be4a))


## v2.14.12 (2026-02-13)


## v2.14.11 (2026-02-13)

### Refactoring

- Rename DEVELOP wave to DELIVER, remove 88 skipped BDD stubs (-4K LOC)
  ([`2d24c4a`](https://github.com/nWave-ai/nwave-dev/commit/2d24c4a4b4dd5fcfd84a40aae6daa4f4379860fa))


## v2.14.10 (2026-02-13)

### Bug Fixes

- **des**: Handle ISO 8601 Z suffix in timeout monitor for Python 3.10
  ([`c3bb340`](https://github.com/nWave-ai/nwave-dev/commit/c3bb340fad7eb4ede6a29f8757db8d1b282e8797))

### Features

- **release**: Production PyPI release train for v1.1.0
  ([`3d41bb6`](https://github.com/nWave-ai/nwave-dev/commit/3d41bb6c64191ce25cb1aea3a011afe10a263aec))

### Refactoring

- **docs**: Move 16 internal-only files to docs/internal/
  ([`5635d3f`](https://github.com/nWave-ai/nwave-dev/commit/5635d3f9072996f453f398c06a459885ceced422))


## v2.14.9 (2026-02-13)

### Bug Fixes

- **ci**: Add project root to pytest pythonpath for scripts module resolution
  ([`540bcfa`](https://github.com/nWave-ai/nwave-dev/commit/540bcfab3a991576d8f186366769674ad7fcbe0e))

- **release**: Bump public_version to 1.0.11 for TestPyPI validation
  ([`f9b995d`](https://github.com/nWave-ai/nwave-dev/commit/f9b995dac91f3bffe772be68b4b61c303ac20907))

- **tests**: Eliminate all 5 remaining skipped DES tests (933 pass, 0 skip)
  ([`f272f4a`](https://github.com/nWave-ai/nwave-dev/commit/f272f4ab55db8618b705451200529723faf0aa81))

- **tests**: Remove hardcoded username from hook portability test comments
  ([`dc8c5f3`](https://github.com/nWave-ai/nwave-dev/commit/dc8c5f3b3f7442beccbb161bad55916696ce9661))

- **tests**: Unskip 20 DES tests and eliminate testing theater (-2700 LOC)
  ([`4fe0520`](https://github.com/nWave-ai/nwave-dev/commit/4fe0520a2ebac3e91745da0afb46ef32a35f01f5))

### Refactoring

- **tests**: Enforce living documentation naming and remove testing theater (-1394 LOC)
  ([`e4dfe3f`](https://github.com/nWave-ai/nwave-dev/commit/e4dfe3ffbe22f287c13decfaf0daa87580a1a55b))

- **tests**: Reorganize tests/ directory structure
  ([`9a98fef`](https://github.com/nWave-ai/nwave-dev/commit/9a98fefec60983cc497c8648d8b26dced692af68))


## v2.14.8 (2026-02-12)

### Bug Fixes

- **ci**: Restrict test matrix to Linux-only to stay within free tier
  ([`89b50be`](https://github.com/nWave-ai/nwave-dev/commit/89b50bed1b61081016a07e623049ecc543edcb9c))

- **release**: Replace dev hatch wheel config instead of skip when present
  ([`85ba640`](https://github.com/nWave-ai/nwave-dev/commit/85ba64007bd429d1a0216029427b80573ee0657f))


## v2.14.7 (2026-02-12)

### Bug Fixes

- **build**: Add explicit hatch wheel packages for CI editable install
  ([`678e9fd`](https://github.com/nWave-ai/nwave-dev/commit/678e9fd9663162f3456b30ed044768e2657f9a1f))

- **ci**: Fix Slack notification payload parsing in release pipeline
  ([`0ec0d48`](https://github.com/nWave-ai/nwave-dev/commit/0ec0d48d16d6a16ff17afb94e6b41ebb19a25757))

- **ci**: Use --skip-lock for pipenv install since Pipfile.lock was removed
  ([`92d82b6`](https://github.com/nWave-ai/nwave-dev/commit/92d82b6b4a2aa4a057bb3c186e2f89650ae36231))

- **deps**: Unify dependencies with pyproject.toml as single source of truth
  ([`ba7e288`](https://github.com/nWave-ai/nwave-dev/commit/ba7e28820bce9ed9b93b89e0f7ba382d9ba3167d))

- **des**: Enable audit logging by default to fix silent failure observability
  ([`52abf67`](https://github.com/nWave-ai/nwave-dev/commit/52abf67190dc3cfa9a082c102fadb6712bccdf01))

- **installer**: Add PyYAML dependency and fix version detection for pipx
  ([`3a51dae`](https://github.com/nWave-ai/nwave-dev/commit/3a51dae026a9ff1fffbad88be6604d6d4ebeb348))

- **installer**: Track nwave_ai CLI package in source repo
  ([`054e6c8`](https://github.com/nWave-ai/nwave-dev/commit/054e6c86f03b5e181a85dd4fdbb50e5deeba80ec))


## v2.14.6 (2026-02-12)

### Bug Fixes

- **release**: Add force-include for scripts/nWave/des in public wheel
  ([`a617c0b`](https://github.com/nWave-ai/nwave-dev/commit/a617c0ba9f3d70fa69f836ae948def3a11e90b1b))

- **release**: Exclude nwave-target/ from rsync to prevent recursive copy
  ([`07d4752`](https://github.com/nWave-ai/nwave-dev/commit/07d4752e0da8fb45d0c4c051e5acef2b3272522e))

### Refactoring

- Rebrand crafter-ai to nwave across entire codebase
  ([`209a4d0`](https://github.com/nWave-ai/nwave-dev/commit/209a4d03672e59656d265c17281c1436c79d8e7e))


## v2.14.5 (2026-02-12)

### Bug Fixes

- **release**: Sync pyproject.toml to public repo and patch identity fields
  ([`7b0ed7a`](https://github.com/nWave-ai/nwave-dev/commit/7b0ed7a1bb1247fda0697a6422152a69c089070a))


## v2.14.4 (2026-02-12)

### Bug Fixes

- **release**: Treat rsync exit code 24 as success in nwave sync
  ([`04369dc`](https://github.com/nWave-ai/nwave-dev/commit/04369dc2b7ba778df731214dd91f4d96752c934c))


## v2.14.3 (2026-02-12)

### Bug Fixes

- **release**: Use rglob to find agents/commands in dist/ nested layout
  ([`9f534a9`](https://github.com/nWave-ai/nwave-dev/commit/9f534a942a4176bb02f46939a6ff348cb37a008c))


## v2.14.2 (2026-02-12)

### Bug Fixes

- **release**: Fix validate_source() tasks/nw bug and rename to create_github_tarballs.py
  ([`e2dd4de`](https://github.com/nWave-ai/nwave-dev/commit/e2dd4dedc263539dd4bd254c1ddd46bf722c527e))

- **release**: Replace broken --force with PSR --patch/--minor/--major flags
  ([`b7d2b14`](https://github.com/nWave-ai/nwave-dev/commit/b7d2b1499d9f701a23714e19e61217f88bbc6cb8))


## v2.14.1 (2026-02-12)

### Bug Fixes

- **installer**: Add des-config.json verification to DES plugin verify()
  ([`6bd2799`](https://github.com/nWave-ai/nwave-dev/commit/6bd2799c6eca2bbc3060064318a4615e8c58431b))

- **installer**: Show des-config.json values and path in verification output
  ([`e71ec48`](https://github.com/nWave-ai/nwave-dev/commit/e71ec4827051da8bd5504121255b2378670d5bc1))

- **installer**: Wire registry.verify_all() into validate_installation()
  ([`8b22e33`](https://github.com/nWave-ai/nwave-dev/commit/8b22e33fb66cdad2d9e0ac6fbd512b880adab33f))


## v2.14.0 (2026-02-12)

### Bug Fixes

- Remove duplicate files recreated by parallel session
  ([`7cdfe76`](https://github.com/nWave-ai/nwave-dev/commit/7cdfe76ff7ed29812ac167a8358590da554c5e8e))

- Resolve all pre-commit hook failures and clean up stale files
  ([`0310fc0`](https://github.com/nWave-ai/nwave-dev/commit/0310fc0f6878906b70bfd2382aed49fabc92cd10))

- **ci**: Use shared scripts for EOF and YAML checks instead of inline
  ([`3ef9b64`](https://github.com/nWave-ai/nwave-dev/commit/3ef9b64172ba79b7d0a555203ba72c1f15071cb7))

- **des**: Extract terminal_phases from raw_data instead of None
  ([`2e91a50`](https://github.com/nWave-ai/nwave-dev/commit/2e91a50f701a3fcde5ba3227dd4ed1cac927b5c3))

- **des**: Parse both v2.0 pipe and v3.0 structured events in integrity verifier
  ([`eba6957`](https://github.com/nWave-ai/nwave-dev/commit/eba695740567b819474b594af67f59a62eb486ac))

- **des**: Support both 'id' and 'step_id' keys in verify_deliver_integrity
  ([`f901315`](https://github.com/nWave-ai/nwave-dev/commit/f901315bc139e09c60ff848674fffb13e47c5a8d))

- **des**: Support nested roadmap format in deliver integrity verifier
  ([`4bff8f2`](https://github.com/nWave-ai/nwave-dev/commit/4bff8f2469a4eac8480fdf906f788074e651521f))

- **des**: Use installed DES CLI path instead of source
  ([`180dfca`](https://github.com/nWave-ai/nwave-dev/commit/180dfca73c11454cd4cf9c09bc91d0ca1d35eb77))

- **installer**: Add schema v4.0 to installation validator
  ([`6b68821`](https://github.com/nWave-ai/nwave-dev/commit/6b68821a4b74d610bb50579e6b34a46a41b47295))

- **lint**: Remove ghost tools/ path, unused noqa directives, and auto-fix mode
  ([`6dbb561`](https://github.com/nWave-ai/nwave-dev/commit/6dbb5613d25f30c38108f811d3d38fad717b5368))

- **nwave**: Apply des-observability retrospective improvements
  ([`7e934ae`](https://github.com/nWave-ai/nwave-dev/commit/7e934aede7ed15d983a8578f911f58b012c93867))

- **release**: Prevent double pipeline runs and unblock PyPI publish
  ([`c2ac1ff`](https://github.com/nWave-ai/nwave-dev/commit/c2ac1ffa434828188203695dabc90f6206cc066e))

- **release**: Pull latest master before syncing public_version back
  ([`f945a63`](https://github.com/nWave-ai/nwave-dev/commit/f945a63090c5862f38061a023158d83320d491b5))

- **roadmap**: Make scaffold and validate steps imperative, not descriptive
  ([`1155465`](https://github.com/nWave-ai/nwave-dev/commit/11554654d51183686dfce405a74ae4ae15596b67))

- **test**: Use tmp_path instead of hardcoded /tmp for Windows compat
  ([`b9fb2cf`](https://github.com/nWave-ai/nwave-dev/commit/b9fb2cff11de6e7efdd96b8422d7be684e808a1c))

### Features

- **build**: Restore build→dist/→install flow with TDD tests
  ([`66ae0f4`](https://github.com/nWave-ai/nwave-dev/commit/66ae0f49c2943b6ccbad1b61df5e82e81539df08))

- **build-pipeline-elimination**: Clean up dist references and force-rebuild flag - step 04-03
  ([`1b86391`](https://github.com/nWave-ai/nwave-dev/commit/1b86391dfa3b9592ca8f3c02b4ae663de2e916f6))

- **build-pipeline-elimination**: Delete build pipeline files - step 03-01
  ([`749794d`](https://github.com/nWave-ai/nwave-dev/commit/749794d2131b37ab1edfd1fcb74b7d73a5bb2342))

- **build-pipeline-elimination**: Delete legacy agents and commands - step 04-01
  ([`f026d6a`](https://github.com/nWave-ai/nwave-dev/commit/f026d6aad012fc9953f93db9c352caa72473a360))

- **build-pipeline-elimination**: Migrate embed data to skills - step 04-04
  ([`1170637`](https://github.com/nWave-ai/nwave-dev/commit/1170637c5fda80b574782870c7d5f2be013ab33c))

- **build-pipeline-elimination**: Remove dist/ide references from test fixtures - step 02-05
  ([`ae45111`](https://github.com/nWave-ai/nwave-dev/commit/ae45111f205ed5f856088075e67c4ac6770751ca))

- **build-pipeline-elimination**: Update CI/CD, release packager, and validation - step 03-02
  ([`600603c`](https://github.com/nWave-ai/nwave-dev/commit/600603c568b28ce59531ddca17adf978fa5f222e))

- **build-pipeline-elimination**: Update framework-catalog.yaml documentation - step 04-02
  ([`9f5d51e`](https://github.com/nWave-ai/nwave-dev/commit/9f5d51edfd9f7a37ed9f06919510cda12d4a6fd0))

- **des**: Add decision logging to handle_pre_write - step 02-01
  ([`829c436`](https://github.com/nWave-ai/nwave-dev/commit/829c436ae2a7c2f96245f8475ced9d252adb0736))

- **des**: Add decision logging to PostToolUse handler
  ([`176464a`](https://github.com/nWave-ai/nwave-dev/commit/176464af8bc74c60c00e3b34dcf965bc714b1fad))

- **des**: Add des-observability roadmap with 12 steps and review fixes
  ([`49fae15`](https://github.com/nWave-ai/nwave-dev/commit/49fae15ee0fee1876ff5729308bfd660883c4838))

- **des**: Add HOOK_COMPLETED event with timing and exit code - step 01-02
  ([`41c2b63`](https://github.com/nWave-ai/nwave-dev/commit/41c2b6334edfde74678b4654211bbfdbc2280788))

- **des**: Add hook_id generation to all four hook adapter handlers - step 01-01
  ([`9f8862b`](https://github.com/nWave-ai/nwave-dev/commit/9f8862b0c3746d795a4691a895cf32f02ac6dd98))

- **des**: Add HOOK_PROTOCOL_ANOMALY events for empty stdin and JSON parse errors
  ([`837ff76`](https://github.com/nWave-ai/nwave-dev/commit/837ff76c91d340ef3e562b753de52fbe9a32f6ed))

- **des**: Add roadmap validator CLI and integrate with deliver integrity
  ([`9512659`](https://github.com/nWave-ai/nwave-dev/commit/9512659577d6d04a1e44e75d48062d6fca4a4b22))

- **des**: Add stderr capture and error_type to HOOK_ERROR events - step 06-01
  ([`0ee2a59`](https://github.com/nWave-ai/nwave-dev/commit/0ee2a591fb6c0cfbd03c7119cb276a793c6b2589))

- **des**: Add task_correlation_id to signal file and HOOK_COMPLETED events - step 05-01
  ([`b11be0a`](https://github.com/nWave-ai/nwave-dev/commit/b11be0ab0efc8cbb24feade7ba83d441a6fff078))

- **des**: Add turns_used and tokens_used execution statistics to phase events - step 07-01
  ([`de6305c`](https://github.com/nWave-ai/nwave-dev/commit/de6305c1f804bcf934bf5ccfcae3b8fd50571df2))

- **des**: Bootstrap des-config.json on install, migrate audit log path
  ([`fab796a`](https://github.com/nWave-ai/nwave-dev/commit/fab796a7551cd89a7fb93d8c68c309942e72882e))

- **des**: Extract agent stats from hook_input and propagate through audit events - step 07-02
  ([`26be730`](https://github.com/nWave-ai/nwave-dev/commit/26be7308da164064d50b25a1df66acd5c2a65ae9))

- **des**: Optimize TDD cycle from 7-phase to 5-phase (schema v4.0)
  ([`ef7cb96`](https://github.com/nWave-ai/nwave-dev/commit/ef7cb960f738866d94308850812b75129bb3d898))

- **des**: Structured YAML execution log format (schema v3.0) - step 08-01
  ([`5aa979f`](https://github.com/nWave-ai/nwave-dev/commit/5aa979f19dd19067eddad0cc93e1d6a6c820f9b2))

- **des**: Thread hook_id from adapter through services to audit events - step 05-02
  ([`10f2486`](https://github.com/nWave-ai/nwave-dev/commit/10f2486b37667007fa26f47b84e280e66d4e5479))

- **nwave**: Integrate Refactoring Priority Premise (RPP) into crafter skills & commands
  ([`31d5648`](https://github.com/nWave-ai/nwave-dev/commit/31d5648d4772d35a1bf0efc5828f01a0fc0c622c))

- **roadmap**: Integrate CLI tools into agent workflow as hard gates
  ([`5b9bd26`](https://github.com/nWave-ai/nwave-dev/commit/5b9bd261dedb9312e381017509196961b6bf598e))

### Performance Improvements

- **test**: Optimize test suite with module-scoped fixtures and batched subprocesses
  ([`1c64313`](https://github.com/nWave-ai/nwave-dev/commit/1c6431321c6e471896598c8a8aff7e6d1f2f3a87))

### Refactoring

- **build-pipeline-elimination**: Deliver phases 3-5 cleanup and review
  ([`36b3729`](https://github.com/nWave-ai/nwave-dev/commit/36b37293ce310f5e6efde9ad53c70b1fc6fa6d07))

- **des**: Extract helpers from extract_des_context_from_transcript
  ([`db11154`](https://github.com/nWave-ai/nwave-dev/commit/db1115489a36959e58cc242ed5524785f9981840))

- **des**: L1-L4 refactoring of hook adapter and subagent stop service
  ([`8da9491`](https://github.com/nWave-ai/nwave-dev/commit/8da94917173919140007eede38f2c296d61ddb11))

- **hooks**: Align pre-commit hooks with CI pipeline behavior
  ([`afd5e1e`](https://github.com/nWave-ai/nwave-dev/commit/afd5e1e653e787e2bb67932906bce0131a130384))

- **installer**: Remove dist_dir from InstallContext
  ([`57f5ba3`](https://github.com/nWave-ai/nwave-dev/commit/57f5ba390c586927038b0ea2f4ab1160d954870c))


## v2.13.3 (2026-02-11)

### Bug Fixes

- **ci**: Nwave-ai release improvements
  ([`5ed30d9`](https://github.com/nWave-ai/nwave-dev/commit/5ed30d9bc03fefb3090a5565ceed7d419232450d))

- **lint**: Resolve ruff errors, fix 13 failing tests, pin ruff in CI
  ([`59a9973`](https://github.com/nWave-ai/nwave-dev/commit/59a99733b78a3f7f21169073db6fe537478e1dd8))


## v2.13.2 (2026-02-11)

### Bug Fixes

- **ci**: Tolerate 'version already exists' on TestPyPI upload
  ([`28a3dea`](https://github.com/nWave-ai/nwave-dev/commit/28a3dea7ac379d14de754ebd6670684c913f4d63))


## v2.13.1 (2026-02-11)

### Bug Fixes

- **ci**: Smoke test from local wheel instead of TestPyPI
  ([`168f4ef`](https://github.com/nWave-ai/nwave-dev/commit/168f4efe4b505dbd42c691a64a05dfc9eacb7f50))


## v2.13.0 (2026-02-11)

### Features

- **ci**: Add smoke test after TestPyPI publish
  ([`7445b71`](https://github.com/nWave-ai/nwave-dev/commit/7445b71733c381b8abcde85cc4cf9b610ea92763))


## v2.12.1 (2026-02-11)

### Bug Fixes

- **ci**: Exclude nwave_ai/ from rsync to preserve CLI package
  ([`44a8261`](https://github.com/nWave-ai/nwave-dev/commit/44a8261275f6b4e26580513e75c1c6c3d5dfa4c8))


## v2.12.0 (2026-02-11)

### Features

- **des**: Audit logging toggle OFF by default with NullObject pattern
  ([`5a67439`](https://github.com/nWave-ai/nwave-dev/commit/5a67439da4ae3484a2310a100c459d3a6b285065))

### Refactoring

- **installer**: Remove build pipeline dependency from install_nwave.py
  ([`f0c4b0e`](https://github.com/nWave-ai/nwave-dev/commit/f0c4b0eed52f6536336e99e91a5dc360ab14f620))


## v2.11.4 (2026-02-10)

### Bug Fixes

- **ci**: Only upload .whl and .tar.gz to TestPyPI
  ([`280ea24`](https://github.com/nWave-ai/nwave-dev/commit/280ea2461c760ad86f6259725fe0e9a58ef658f5))


## v2.11.3 (2026-02-10)

### Bug Fixes

- **ci**: Build wheel directly from source, not via sdist
  ([`5cf5e52`](https://github.com/nWave-ai/nwave-dev/commit/5cf5e5298604a9aef2e4666a89d3dff219e134dd))


## v2.11.2 (2026-02-10)

### Bug Fixes

- **ci**: Build IDE bundle in publish-to-nwave before commit
  ([`223d652`](https://github.com/nWave-ai/nwave-dev/commit/223d652769bab623f3fc5242afb43ada6f110ae1))


## v2.11.1 (2026-02-10)

### Bug Fixes

- **ci**: Build IDE bundle before wheel in publish-to-pypi job
  ([`d7609c3`](https://github.com/nWave-ai/nwave-dev/commit/d7609c3eebbb180c61f67d7b9e117b1ab2e0af0d))


## v2.11.0 (2026-02-10)

### Bug Fixes

- **ci**: Remove dangling symlinks before rsync to prevent exit code 23
  ([`cd4b646`](https://github.com/nWave-ai/nwave-dev/commit/cd4b646cf6389a64cd2db04a6aed8fae37b41516))

### Features

- **des**: Add log_phase CLI and update templates for timestamp enforcement
  ([`ceac3aa`](https://github.com/nWave-ai/nwave-dev/commit/ceac3aab076e134a5b202a6ed0d5eedb2decbc16))

- **des**: Add zero-trust timestamp correction to SubagentStopService
  ([`d35ff55`](https://github.com/nWave-ai/nwave-dev/commit/d35ff55994e544257da777fd286617e11de704a8))

### Refactoring

- **installer**: Simplify agents_plugin to read from nWave/agents/ directly
  ([`ea21266`](https://github.com/nWave-ai/nwave-dev/commit/ea2126693a7cf5fc1f1cf26ed7904bffc2ff2c61))

- **installer**: Simplify commands_plugin to read from nWave/tasks/nw/ directly
  ([`afbdba0`](https://github.com/nWave-ai/nwave-dev/commit/afbdba0950a3b8757a2c8a2e83a72197edbc0114))


## v2.10.3 (2026-02-10)

### Bug Fixes

- **release**: Resolve symlinks in rsync with -L flag for wheel build
  ([`08be762`](https://github.com/nWave-ai/nwave-dev/commit/08be7621a6710ca5d8a4a36ec024638e3403ea1f))


## v2.10.2 (2026-02-10)

### Bug Fixes

- **release**: Exclude .github/ from nwave rsync to avoid workflow scope error
  ([`8004503`](https://github.com/nWave-ai/nwave-dev/commit/80045034da3e2f6d5b738e8c7f9591d2777133de))


## v2.10.1 (2026-02-10)

### Bug Fixes

- **release**: Checkout version tag in build job after dispatch bump
  ([`753507a`](https://github.com/nWave-ai/nwave-dev/commit/753507aa669b20f1ebabdf6d0069e19549845783))


## v2.10.0 (2026-02-10)

### Bug Fixes

- **release**: Use --print for PSR 10.x dry run (--noop removed)
  ([`4e121cc`](https://github.com/nWave-ai/nwave-dev/commit/4e121cce59fb7c075e7a4754ffd32012cb5ce42d))

### Features

- **des**: Add RECORDING_INTEGRITY as 9th mandatory section + Testing Theater prevention
  ([`0bc132f`](https://github.com/nWave-ai/nwave-dev/commit/0bc132fd3c9ea8d5249b0ffd9bbc17d6f756dab2))

- **release**: Add PyPI publishing and nwave-ai package support
  ([`3e7de2a`](https://github.com/nWave-ai/nwave-dev/commit/3e7de2aa02dc3e42e923ca4a527967900c839261))

### Refactoring

- **ci**: Split monolithic pipeline into CI and Release workflows
  ([`ee3ec1d`](https://github.com/nWave-ai/nwave-dev/commit/ee3ec1d02455eef196b0829617c23c44c1e4e500))


## v2.9.0 (2026-02-10)

### Bug Fixes

- **des**: Decouple future-timestamp check from task_start_time and namespace signal files
  ([`edb6716`](https://github.com/nWave-ai/nwave-dev/commit/edb671677a1d8e6af9cbe0a059f62f41e41cd128))

- **format**: Ruff format 2 files previously outside pre-commit scope
  ([`d04b154`](https://github.com/nWave-ai/nwave-dev/commit/d04b1549e3eaa0b6d5267627736d606b5087b7a9))

- **lint**: Auto-fix remaining ruff errors in 4 Alessandro test files
  ([`47d62bc`](https://github.com/nWave-ai/nwave-dev/commit/47d62bc4c847d8408b3bc4ca06d21b0a451b2bab))

- **quality**: Add src/ to ruff pre-commit scope and fix lint + test errors
  ([`5353791`](https://github.com/nWave-ai/nwave-dev/commit/5353791f73eac420d212edd1669b15be3bcc4136))

- **tests**: Correct parent path depth in hook resilience subprocess tests
  ([`e6e1d85`](https://github.com/nWave-ai/nwave-dev/commit/e6e1d85f448a8f146c5812fad3cc715e9c2710bd))

### Features

- **build-pipeline-elimination**: Add CI frontmatter lint validation - step 01-03
  ([`984ca77`](https://github.com/nWave-ai/nwave-dev/commit/984ca7731c500fd12aa3c619c63bc9cdde9e5415))

- **build-pipeline-elimination**: Verify agent frontmatter completeness
  ([`641d125`](https://github.com/nWave-ai/nwave-dev/commit/641d1256e0dd02649fc6bb3e8d779f0cb75e67b7))

- **commands**: Add YAML frontmatter to all 18 command source files - step 01-01
  ([`8ade8b1`](https://github.com/nWave-ai/nwave-dev/commit/8ade8b1aa669385181160c6a693e2ae4b5181967))

- **des**: Add log integrity validator and hook resilience
  ([`0e18211`](https://github.com/nWave-ai/nwave-dev/commit/0e1821164c89b3c3243197316d1f4616dd5940b1))

- **reports**: Add Allure, HTML branding, Rich domain table and CI artifacts
  ([`865dd24`](https://github.com/nWave-ai/nwave-dev/commit/865dd245cd1d29c71d15f13212c158f5404b0539))

- **roadmap**: Add build pipeline elimination roadmap
  ([`124d4a2`](https://github.com/nWave-ai/nwave-dev/commit/124d4a219c39a0ff3bd3f460da9be79fa61eda82))

### Refactoring

- **tests**: Reorganize test tree by domain with layer pyramid
  ([`6a48280`](https://github.com/nWave-ai/nwave-dev/commit/6a482803481a97c88dd7445afab31962358e0609))


## v2.8.0 (2026-02-10)

### Bug Fixes

- **tests**: Update hook counts and fixtures for DES session guard
  ([`127c33a`](https://github.com/nWave-ai/nwave-dev/commit/127c33ae50de5482124de9dcd09c3e45083ad9c2))

### Features

- **agents**: Add git branching strategy decision to devops workflow
  ([`78769e4`](https://github.com/nWave-ai/nwave-dev/commit/78769e4a30d3d59ac15e4e179c62818a86d211e9))

- **agents**: Add merge workflow to agent-builder (Zeus)
  ([`2409cd0`](https://github.com/nWave-ai/nwave-dev/commit/2409cd0cb8db762f5b37d32a52d86f9141fa2f57))

- **agents**: Add user centricity and outside-in principles to acceptance-designer
  ([`4ff5546`](https://github.com/nWave-ai/nwave-dev/commit/4ff5546654d5e5134c3c2c22c2376be2410ef274))

- **agents**: Restore lost researcher knowledge as skills and optimize agent
  ([`4ec3cc0`](https://github.com/nWave-ai/nwave-dev/commit/4ec3cc05bc390cc23f98cdbc9aba1b03eaf604ad))

- **des**: BLINDARE — DES enforcement hardening with portable hooks
  ([`2e84825`](https://github.com/nWave-ai/nwave-dev/commit/2e848259976aa745a40594d567f88c55c9b9e34d))

- **installer**: Validate skills and DES presence in verification
  ([`f960aa0`](https://github.com/nWave-ai/nwave-dev/commit/f960aa063e0196c00929e62c0849f513f0bd1a54))

### Refactoring

- **agents**: Merge leanux-designer into product-owner (Luna)
  ([`51594be`](https://github.com/nWave-ai/nwave-dev/commit/51594be5af25d9758d0cc0c7c0e54f0035eed93b))

- **agents**: Optimize acceptance-designer 271→185 lines
  ([`93482b3`](https://github.com/nWave-ai/nwave-dev/commit/93482b36b274afb1f57de81a10fbc2170d9827c4))

- **agents**: Remove devop agent artifacts, relocate skills
  ([`6e348b5`](https://github.com/nWave-ai/nwave-dev/commit/6e348b5618f72edfd3e332bb80666b1575078f37))


## v2.7.0 (2026-02-09)

### Features

- **skills**: Add JTBD/ODI skills for product-owner from git history extraction
  ([`09bf7f1`](https://github.com/nWave-ai/nwave-dev/commit/09bf7f18a87ae64486497373a5ac6e865c2e92d1))


## v2.6.0 (2026-02-09)

### Bug Fixes

- **commands**: Use production paths (~/.claude/) instead of source-tree paths
  ([`bfd4d97`](https://github.com/nWave-ai/nwave-dev/commit/bfd4d975aa90a431855aa1e8276bdcd3bf3ba2d8))

### Features

- **skills**: Add 5 reviewed software-crafter skills from legacy knowledge extraction
  ([`4c938f7`](https://github.com/nWave-ai/nwave-dev/commit/4c938f79f09b9ca4864cd5f478751aea377b062e))


## v2.5.1 (2026-02-09)

### Bug Fixes

- **tests**: Ruff format test_wrapper_plugins.py after rename
  ([`994ba58`](https://github.com/nWave-ai/nwave-dev/commit/994ba58478ecec56153cf8ac5520ba05efdfc433))

- **tests**: Update test fixtures from develop.md to devop.md after wave rename
  ([`cc1a8b8`](https://github.com/nWave-ai/nwave-dev/commit/cc1a8b88987512ecee0e747189fb7cd330718106))

### Refactoring

- **nwave**: Merge nw-devop into nw-platform-architect, rename waves DEVOP/DELIVER
  ([`8c0ea45`](https://github.com/nWave-ai/nwave-dev/commit/8c0ea4569d768132a56d4bb228a37da3aea3f6b7))


## v2.5.0 (2026-02-09)

### Features

- **des**: Inject DES continuation context in PostToolUse hook
  ([`f6a6e9e`](https://github.com/nWave-ai/nwave-dev/commit/f6a6e9e8ecf1268c22b212c5d3a8d3298f9ce019))


## v2.4.0 (2026-02-08)

### Bug Fixes

- **des**: Add diagnostic audit logging to all hook handlers
  ([`0bb2610`](https://github.com/nWave-ai/nwave-dev/commit/0bb2610ee6748a0d8e4020811dcad218dc19aa94))

- **des**: Prevent execution-log fraud and enforce agent-only phase recording
  ([`fdc2379`](https://github.com/nWave-ai/nwave-dev/commit/fdc2379b210eddf95e8c91b7a5b17316f939a09a))

- **des**: Resolve ruff import sorting and type-checking violations
  ([`bbd58cc`](https://github.com/nWave-ai/nwave-dev/commit/bbd58cc42338a5ec1674e55118d56a2cd696ce88))

### Features

- **des**: Add git commit verification to SubagentStop hook (Layer 1)
  ([`3d7a759`](https://github.com/nWave-ai/nwave-dev/commit/3d7a759f06a7c52dfb795e0fac75e55e47d596b3))

### Refactoring

- **commands**: Apply best-practice audit fixes across 18 files
  ([`60eef45`](https://github.com/nWave-ai/nwave-dev/commit/60eef45075ab7994a754ca8a28ff6fa83517fbba))


## v2.3.1 (2026-02-08)

### Bug Fixes

- **commands**: Standardize NW- prefix, add design questions, deduplicate DES
  ([`832d47f`](https://github.com/nWave-ai/nwave-dev/commit/832d47f4f6f44018ae808c035acd88c4150f8406))


## v2.3.0 (2026-02-08)

### Bug Fixes

- **distill**: Generalize interactive questions, remove nWave-specific terms
  ([`82ba778`](https://github.com/nWave-ai/nwave-dev/commit/82ba778e65a02de97625fe574a5ad6491813d090))

### Features

- **distill**: Add bug fix test structure and hexagonal testing principles
  ([`2edea46`](https://github.com/nWave-ai/nwave-dev/commit/2edea4627714a1ba244305950505efbe423b2094))

- **workflow**: Restructure waves, add DES markers, L1-L4 refactoring
  ([`4a63047`](https://github.com/nWave-ai/nwave-dev/commit/4a63047cf21eaae24a2ec2f4d328195de1efb312))


## v2.2.0 (2026-02-08)

### Bug Fixes

- **ci**: Remove nul file breaking Windows checkout
  ([`be56767`](https://github.com/nWave-ai/nwave-dev/commit/be56767f9fb8883df8ac18bacf3711afa8d04fac))

- **hooks**: Use venv Python path instead of system python3
  ([`84d045d`](https://github.com/nWave-ai/nwave-dev/commit/84d045db47d45d2b0e42f89b31b3aa964eaae095))

### Features

- **framework**: Migrate to skill-based v2 architecture
  ([`d63bb2d`](https://github.com/nWave-ai/nwave-dev/commit/d63bb2d035eabf59ccb11e1488585f214bb92ede))


## v2.1.0 (2026-02-07)

### Bug Fixes

- **ci**: Resolve ruff lint errors and relax gitlint title regex
  ([`888586b`](https://github.com/nWave-ai/nwave-dev/commit/888586b807215677134592ffbe6e1d46557e7858))

### Features

- **audit-log**: Validate step 01-01 port layer implementation
  ([`51b4f19`](https://github.com/nWave-ai/nwave-dev/commit/51b4f19d3b323bbfd65c4c0a6d66e8b0b6cd7565))

- **audit-log-refactor**: Add BDD tests for hook enforcement audit schema - step 05-02
  ([`4cb451b`](https://github.com/nWave-ai/nwave-dev/commit/4cb451baee88369316cb3c02fe3c7776b9e0bd79))

- **audit-log-refactor**: Verify legacy tests migrated - step 04-01
  ([`d6d86f8`](https://github.com/nWave-ai/nwave-dev/commit/d6d86f81cbf8a636aa50e45874f18e3f7b78f13a))

### Refactoring

- **des**: L1 - naming clarity improvements
  ([`5bb13d3`](https://github.com/nWave-ai/nwave-dev/commit/5bb13d37bc996f4585d56e28a96e5ff10d978766))

- **des**: L2 - complexity reduction
  ([`5334689`](https://github.com/nWave-ai/nwave-dev/commit/5334689b5a44e1fc669a7eecef45cab927070b5b))

- **des**: L3 - class responsibility reorganization
  ([`ef9dcb1`](https://github.com/nWave-ai/nwave-dev/commit/ef9dcb1773f7b3d3d8aadbd10bd6eead32d115a9))

- **des**: L4 - architecture pattern improvements
  ([`ef994ac`](https://github.com/nWave-ai/nwave-dev/commit/ef994acceffed8411cbae84deefcf3b0ae8a59a7))


## v2.0.4 (2026-02-07)

### Bug Fixes

- **ci**: Remove missing installer .py from release artifacts
  ([`56890f9`](https://github.com/nWave-ai/nwave-dev/commit/56890f9cdd7f733dc5cf6b8083d6ecfb57491da6))


## v2.0.3 (2026-02-07)

### Bug Fixes

- **ci**: Remove [skip ci] from PSR commit message
  ([`70f9c1f`](https://github.com/nWave-ai/nwave-dev/commit/70f9c1f4865a254ab7c9ea8ab63f0e7c5b0aabee))


## v2.0.2 (2026-02-07)

### Bug Fixes

- **ci**: Configure PSR commit author and prevent duplicate pipelines
  ([`33ee3fd`](https://github.com/nWave-ai/nwave-dev/commit/33ee3fd52adc0cc921696b2e8352cb591ce4dd7a))

- **ci**: Remove invalid --clean flag from build_ide_bundle invocation
  ([`f298866`](https://github.com/nWave-ai/nwave-dev/commit/f298866dc95572a9a1d6adcfbf8321634bcc40a2))


## v2.0.1 (2026-02-07)

### Bug Fixes

- **ci**: Make PSR version commits pass commitlint validation
  ([`6b3dc94`](https://github.com/nWave-ai/nwave-dev/commit/6b3dc9470bf08564c2fb1a9e893f1fb19e3fe1cf))


## v2.0.0 (2026-02-07)

### Bug Fixes

- Add missing split.md to nWave/tasks/nw
  ([`dd94570`](https://github.com/nWave-ai/nwave-dev/commit/dd94570a36585d0f5ba57b92978592b20897df3e))

- Enforce LF line endings for shell scripts (Windows CI/CD)
  ([`43d0f11`](https://github.com/nWave-ai/nwave-dev/commit/43d0f1190b5f7162fbb8eeac1c80531c7886f3ca))

- Fix 5 failing tests due to DESOrchestrator DI refactoring
  ([`ece30d5`](https://github.com/nWave-ai/nwave-dev/commit/ece30d55c595276399bbb04e144491f769b2dbc3))

- Python 3.8 compatibility for type hints in test_path_traversal.py
  ([`5c912ac`](https://github.com/nWave-ai/nwave-dev/commit/5c912acb3d5eb6323758a418f8ee717c9a6e4308))

- Remove .claude/settings.local.json
  ([`ffd0a0b`](https://github.com/nWave-ai/nwave-dev/commit/ffd0a0b2c7deb7dfbeefaf25c59fb71ed269e42a))

- Remove pip cache from CI/CD workflow (no requirements.txt)
  ([`4a7324c`](https://github.com/nWave-ai/nwave-dev/commit/4a7324cac6c16fa6edce910f5545e49dd0e2d6fb))

- Windows Unicode encoding in CI/CD pre-commit hooks
  ([`d9daac0`](https://github.com/nWave-ai/nwave-dev/commit/d9daac0240c337a59ae888138b1356da91c45f61))

- **agents**: Add STEP 1.7 subagent execution mode to prevent confirmation loops
  ([`4fc5e73`](https://github.com/nWave-ai/nwave-dev/commit/4fc5e736977bfc599f09f7d086bc58df15004859))

- **backup**: Selective backup of nwave config files only, skip for fresh installs
  ([`ef8529f`](https://github.com/nWave-ai/nwave-dev/commit/ef8529ff2bb9f111bc67f9e0c8adc6e661e20b1c))

- **build**: Clean dist directory by default to prevent stale artifacts
  ([`a8fc4c3`](https://github.com/nWave-ai/nwave-dev/commit/a8fc4c310c4bf5eaa7587fb1d06a55ea33989503))

- **ci**: Add packaging dependency for framework validation
  ([`ec362fd`](https://github.com/nWave-ai/nwave-dev/commit/ec362fd65bbc577a0a9a3ab5d6b1afd35b6d584c))

- **ci**: Align local and remote quality gates with ruff
  ([`ce9ca2b`](https://github.com/nWave-ai/nwave-dev/commit/ce9ca2bf25132ed8ba7899fffbad5866a869dcd8))

- **ci**: Build IDE bundle before running tests
  ([`15cc663`](https://github.com/nWave-ai/nwave-dev/commit/15cc663fe401dd9730f77cca7dbc7b06c9fbbbab))

- **ci**: Correct PSR config: build_command type and changelog path
  ([`554ec20`](https://github.com/nWave-ai/nwave-dev/commit/554ec20e7846bf7ab4cc0d7f5882b299b18d44e9))

- **ci**: Enable UTF-8 mode for Windows Unicode support
  ([`de1be93`](https://github.com/nWave-ai/nwave-dev/commit/de1be93e7a9d27c94d67057bbb1cf60926ba3471))

- **ci**: Handle git history rewrites in commit validation
  ([`6609332`](https://github.com/nWave-ai/nwave-dev/commit/6609332e58a9731fc5d7ca7e80ca303d4ce45e66))

- **ci**: Prevent shell injection in Slack commit message truncation
  ([`ef30ea2`](https://github.com/nWave-ai/nwave-dev/commit/ef30ea2a7a9c15241984d1b4fd1558775de621d9))

- **ci**: Remove invalid --clean flag from build_ide_bundle
  ([`086e518`](https://github.com/nWave-ai/nwave-dev/commit/086e5188e7df957a3f2e86e07d3ef3108a45375e))

- **ci**: Replace exception anti-pattern with platform detection
  ([`dc93564`](https://github.com/nWave-ai/nwave-dev/commit/dc935640ad480fa1ec9706e93ce5e68054d7a3df))

- **ci**: Resolve dependency desync and linting issues
  ([`50393db`](https://github.com/nWave-ai/nwave-dev/commit/50393dba0e79c80f48436a52b6c9215c8c93d523))

- **ci**: Skip hook existence test in CI and fix ruff-format
  ([`4eea96a`](https://github.com/nWave-ai/nwave-dev/commit/4eea96aa78677a922fad992d5cf2323529be2bcf))

- **ci**: Testpypi publish and windows timeout issues
  ([`652e40d`](https://github.com/nWave-ai/nwave-dev/commit/652e40db59203b8ed2c00dc27737648831f76b76))

- **ci**: Use pipenv for Python deps and fix cross-platform hooks
  ([`623051e`](https://github.com/nWave-ai/nwave-dev/commit/623051ee580408ad1acf4c443da39b3db2357cae))

- **ci**: Use Pipfile as single source of truth for dependencies
  ([`2600cd8`](https://github.com/nWave-ai/nwave-dev/commit/2600cd8bcdf04344f52495dab844fce014bbc8bb))

- **ci**: Version-control commit-msg hook and copy in CI
  ([`76b1955`](https://github.com/nWave-ai/nwave-dev/commit/76b1955abef40f3795d9d42db70aec5ef48ab383))

- **ci-cd**: Add installer branch to workflow triggers
  ([`d67fd88`](https://github.com/nWave-ai/nwave-dev/commit/d67fd88ba69acc5cf9feb66f44607bf324193896))

- **ci-cd**: Correct Slack action parameters
  ([`939f6c4`](https://github.com/nWave-ai/nwave-dev/commit/939f6c413137289222dbcdbd32f6a8f71641f70c))

- **cli**: Block install on pre-flight failures with clean error message
  ([`4716828`](https://github.com/nWave-ai/nwave-dev/commit/4716828a97a269dbc099b93d10a1ba48ba908b81))

- **cli**: Wire build to install - call forge install after successful build
  ([`e804874`](https://github.com/nWave-ai/nwave-dev/commit/e8048745cbef4730b6bf0b39d618b21b2a006b5a))

- **cli**: Wire CheckRegistry to CheckExecutor in forge build
  ([`df1228f`](https://github.com/nWave-ai/nwave-dev/commit/df1228fb3c54a24ad9b0db12aec4350268e4c788))

- **cli**: Wire GitPort to VersionBumpService in forge build
  ([`08ac0ef`](https://github.com/nWave-ai/nwave-dev/commit/08ac0ef7f81bba2a0479c4fc80c55f88400b23dd))

- **constants**: Update expected counts to match actual nWave source
  ([`61e0adc`](https://github.com/nWave-ai/nwave-dev/commit/61e0adcf7061a40838edaaaa9975bb1fdba56fca))

- **des**: Add config file support for audit log directory resolution
  ([`8729f78`](https://github.com/nWave-ai/nwave-dev/commit/8729f782632ea909339ef13a6f2abcf1895639fe))

- **des**: Add max_turns validation in PreToolUse hook
  ([`87c9155`](https://github.com/nWave-ai/nwave-dev/commit/87c9155cbc82f60c563b85fe834e67de981c9dca))

- **des**: Address 3 priority review conditions (v1.4 → v1.4.1)
  ([`494e442`](https://github.com/nWave-ai/nwave-dev/commit/494e442415e36e93542a84777e36a061e9061438))

- **des**: Address all architecture review issues (1 CRITICAL + 4 HIGH)
  ([`a9cb42d`](https://github.com/nWave-ai/nwave-dev/commit/a9cb42dbf6a20491569d0ed65ada3b3c24958f30))

- **des**: Clear bytecode cache on reinstall + add PostToolUse to DES plugin
  ([`7873b5b`](https://github.com/nWave-ai/nwave-dev/commit/7873b5bbd22d9ca203a905cf05c59404c82509a4))

- **des**: Complete test suite cleanup - remove duplicate test files and fix imports
  ([`02cfc7d`](https://github.com/nWave-ai/nwave-dev/commit/02cfc7d1a1a7d97ff151526256580b3bfcb5477a))

- **des**: Correct architecture with real SubagentStop hook schema (v1.5.0)
  ([`087ea4a`](https://github.com/nWave-ai/nwave-dev/commit/087ea4a0126710307033970d3691ab2249136f8d))

- **des**: Correct component boundaries with real SubagentStop hook schema (v1.5.0)
  ([`099b138`](https://github.com/nWave-ai/nwave-dev/commit/099b138687f739912bba95020a60aa58638e1b53))

- **des**: Correct data models with real SubagentStop hook schema (v1.5.0)
  ([`44e67f4`](https://github.com/nWave-ai/nwave-dev/commit/44e67f4e6aaa97fca9b52b02e5e36559d313951e))

- **des**: Correct discovery report with real SubagentStop hook data (v2.0)
  ([`f8496db`](https://github.com/nWave-ai/nwave-dev/commit/f8496dbb24dd30aa8ec981afb6f9e206adfc7375))

- **des**: Correct remaining design docs with real SubagentStop hook schema (v1.5.0)
  ([`79bacc9`](https://github.com/nWave-ai/nwave-dev/commit/79bacc9db07b979cd5bd1571a9708fcd34970f28))

- **des**: Fix 3 test failures in template validation
  ([`72857dd`](https://github.com/nWave-ai/nwave-dev/commit/72857dd4f0ba1b4c52c260481c6bed0ead3589b1))

- **des**: Fix linting errors and apply code formatting
  ([`2c5ae4a`](https://github.com/nWave-ai/nwave-dev/commit/2c5ae4a28dd63258fdd2ae69b1dbf01f6d237c8c))

- **des**: Fix PreToolUse hook max_turns validation and installation
  ([`17db3fc`](https://github.com/nWave-ai/nwave-dev/commit/17db3fc4c918a0f2ef3d95c6164f9b6af8872253))

- **des**: Fix schema path resolution for installed DES hooks
  ([`7bb8d9d`](https://github.com/nWave-ai/nwave-dev/commit/7bb8d9d33c754de0d9b1708dcf47defd662e34aa))

- **des**: Fix scope violation in E2E wiring test and enhance ExecuteStepResult
  ([`5fb2702`](https://github.com/nWave-ai/nwave-dev/commit/5fb2702849979d18100a9aed5da84bfebf74692d))

- **des**: Fix SubagentStop protocol to match Claude Code's actual format
  ([`48b2910`](https://github.com/nWave-ai/nwave-dev/commit/48b29106440997fb5e9cb5ea3878193a8b09d28f))

- **des**: Fix validation logic and test failures for US-001, US-002, US-003
  ([`dd0e059`](https://github.com/nWave-ai/nwave-dev/commit/dd0e059767169ab803c9e8c7bc49b7e193551ec4))

- **des**: Implement all 5 software-crafter-reviewer improvements (v1.6.0)
  ([`b0e8deb`](https://github.com/nWave-ai/nwave-dev/commit/b0e8debb75589d0fcc85aafef603756e4291954d))

- **des**: Improve hook detection for both old and new command formats
  ([`c8fe1fb`](https://github.com/nWave-ai/nwave-dev/commit/c8fe1fb7625541de6d02ac0e043963478bcce65c))

- **des**: Improve template path resolution for installed location
  ([`af46b02`](https://github.com/nWave-ai/nwave-dev/commit/af46b02700ed2cd9b78063894a5b6aed1be84cbb))

- **des**: Normalize path separators for cross-platform compatibility
  ([`ab21b9c`](https://github.com/nWave-ai/nwave-dev/commit/ab21b9cb3aa2d35407b0112e378e383bd7324479))

- **des**: Read tool_input from top-level Claude Code protocol
  ([`42476cb`](https://github.com/nWave-ai/nwave-dev/commit/42476cbb52cdd137f1f177a46e092b72c8ef918b))

- **des**: Replace from src.des imports with from des for portable package
  ([`25637d0`](https://github.com/nWave-ai/nwave-dev/commit/25637d09d4ffc213b307c013c839b590d3f87ae0))

- **des**: Resolve all 6 blocking issues in installation architecture (v1.2)
  ([`e4ac377`](https://github.com/nWave-ai/nwave-dev/commit/e4ac37782fdffa491ec67463fdac1604b507f89c))

- **des**: Resolve DISTILL review critical issues - proper Outside-In TDD RED state
  ([`1560575`](https://github.com/nWave-ai/nwave-dev/commit/1560575049b09451b7f7776dbc6fdbfb61ff8812))

- **des**: Resolve DoR critical blocker - add SubagentStop hook empirical evidence
  ([`30b9850`](https://github.com/nWave-ai/nwave-dev/commit/30b9850f8c5128c9027480b0c12dce455017b98e))

- **des**: Resolve installation bugs and harden security
  ([`48378cc`](https://github.com/nWave-ai/nwave-dev/commit/48378cc3bad25f5ce18dbb9b08ecba9d916f5265))

- **des**: Resolve Q1 with empirical SubagentStop hook verification
  ([`49243a7`](https://github.com/nWave-ai/nwave-dev/commit/49243a7b8d14f8096242fbf1f7ee4fcf9e57ee1d))

- **des**: Restore render_full_prompt method lost in merge conflict
  ([`ee92d44`](https://github.com/nWave-ai/nwave-dev/commit/ee92d44f166301f5529cfde6d5c679535284d55b))

- **des**: SubagentStop must exit 0 with decision:block for context injection
  ([`c5ac2e9`](https://github.com/nWave-ai/nwave-dev/commit/c5ac2e944ffb64a196e418ff714682017d6c9d39))

- **des**: Use installed path for hooks instead of dev location
  ([`3658ae9`](https://github.com/nWave-ai/nwave-dev/commit/3658ae91e5e6166107d513fa324e9775d87a7903))

- **des-hook-enforcement**: Clear audit log for test isolation when audit disabled
  ([`1146dd3`](https://github.com/nWave-ai/nwave-dev/commit/1146dd31bb4cc77de51ead53b7d41e2613266e88))

- **des-hook-enforcement**: Update scope violation tests for HOOK_SUBAGENT_STOP coexistence
  ([`8c0cb44`](https://github.com/nWave-ai/nwave-dev/commit/8c0cb444200d380a50d9b87620d75be4fea823c8))

- **des-plugin**: Cross-platform path escaping in verify method
  ([`4c1e7f7`](https://github.com/nWave-ai/nwave-dev/commit/4c1e7f741ae6a34293f9a117c74dbaeac8e3d258))

- **des-us003**: Update step 01-04 COMMIT phase to PASS
  ([`6708eb2`](https://github.com/nWave-ai/nwave-dev/commit/6708eb22daa2f11d6bdcd3b6657f13b324195b69))

- **des-us007**: Clarify mutation testing gate in develop.md workflow
  ([`e6f0ee4`](https://github.com/nWave-ai/nwave-dev/commit/e6f0ee4a62b50549c59ff305362722f65311cba4))

- **docs**: Repair YAML syntax in roadmap acceptance_criteria
  ([`5a05a76`](https://github.com/nWave-ai/nwave-dev/commit/5a05a76078b9777e4c9f70ab2645b38287f8dc2a))

- **forge-install**: Align auto-chain build with TUI design
  ([`0ceb8f3`](https://github.com/nWave-ai/nwave-dev/commit/0ceb8f343ea5e86c2415a0ce10632b098fa8a742))

- **forge-install**: Make validation error message user-friendly
  ([`a928d71`](https://github.com/nWave-ai/nwave-dev/commit/a928d71bf8faf50eafcbf30b3279f38e2e6ddd9e))

- **forge-install**: Match Luna's design for CLI install completion line
  ([`157632b`](https://github.com/nWave-ai/nwave-dev/commit/157632b38146ee16ba35f77b414b4af15ef4ef28))

- **forge-install**: Show all install details even on failure
  ([`1effd29`](https://github.com/nWave-ai/nwave-dev/commit/1effd29fe453b0ef509d81ded3df43fb4ba64f05))

- **forge-install**: Update nWave slogan to match brand
  ([`cb4acaa`](https://github.com/nWave-ai/nwave-dev/commit/cb4acaa8e7119c20d2b08b4d95df85945814a1ee))

- **forge-install**: Use correct DeploymentValidationResult attributes
  ([`f1a608e`](https://github.com/nWave-ai/nwave-dev/commit/f1a608e21dd57b6eaa5867ba6e200112adb395d7))

- **install**: Accept schema v3.0 (7 phases) in validator
  ([`1217cca`](https://github.com/nWave-ai/nwave-dev/commit/1217cca682f0e7c82e6901af0fa4a4864724f410))

- **install**: Add log line for verification counts
  ([`eb8ba9f`](https://github.com/nWave-ai/nwave-dev/commit/eb8ba9f872e7e04f7e00f7e7fdf893e80ebcc1fc))

- **install**: Add schema validation and force-rebuild option
  ([`f0ef976`](https://github.com/nWave-ai/nwave-dev/commit/f0ef9764c63f4f148259b0e105d17d75c3457c25))

- **install**: Correct build script path in install_nwave.py
  ([`9f01f46`](https://github.com/nWave-ai/nwave-dev/commit/9f01f46b789d95647dea5a23888d6a2df13a719e))

- **install**: Correct build script path in install_nwave.py
  ([`8d2a3a4`](https://github.com/nWave-ai/nwave-dev/commit/8d2a3a49c40b16c74761e015280a8641bd0023ee))

- **install**: Install all template files not just schema
  ([`14f3349`](https://github.com/nWave-ai/nwave-dev/commit/14f3349efc132fd636f07750e40fbda8de138198))

- **install**: Remove legacy commit.md validation reference
  ([`d22850f`](https://github.com/nWave-ai/nwave-dev/commit/d22850f93e9a7e00e84c68c7db441ad7bf2ad224))

- **install**: Resolve version and install path via pipx list_packages fallback
  ([`0b27161`](https://github.com/nWave-ai/nwave-dev/commit/0b271613fce8c1ffa4105776b81a86cd09799404))

- **installer**: Add /nw:discover to installation summary
  ([`982df5b`](https://github.com/nWave-ai/nwave-dev/commit/982df5b0213990f81d8db5f99c185fac262a5747))

- **installer**: Add contract tests and error-specific fix messages
  ([`598b83b`](https://github.com/nWave-ai/nwave-dev/commit/598b83bacb3d9c41ce4bebf7348bfaff87692ed2))

- **installer**: Align IDE bundle constants and tests with actual nWave structure
  ([`817d3f6`](https://github.com/nWave-ai/nwave-dev/commit/817d3f69fcd8ea28b4e0fdac5a73b724015ac363))

- **installer**: Resolve deployment path mismatch (agents/nw, commands/nw, scripts)
  ([`81c6393`](https://github.com/nWave-ai/nwave-dev/commit/81c6393e52bb85550b8653fd849036e646da1d3b))

- **installer**: Resolve manifest circular dependency bug
  ([`54d5563`](https://github.com/nWave-ai/nwave-dev/commit/54d5563ab945ccac0cd74cf828f60bea4d2b4c42))

- **lint**: Apply ruff formatting to all project files
  ([`072f716`](https://github.com/nWave-ai/nwave-dev/commit/072f7164cfc8dc00da08f2a94290accfcbd8dbbb))

- **lint**: Correct noqa placement for E402 import
  ([`4df5f07`](https://github.com/nWave-ai/nwave-dev/commit/4df5f07d39800179e25f194ce19194df076d1f7d))

- **lint**: Format remaining files from merge and fix unused variable
  ([`e04a78e`](https://github.com/nWave-ai/nwave-dev/commit/e04a78eae557aa935186afce1dd0faaebea59f5f))

- **lint**: Resolve ruff lint errors across test files
  ([`3921c4a`](https://github.com/nWave-ai/nwave-dev/commit/3921c4a3a74b3fbb1754161b75eadb0454407ce7))

- **lint**: Suppress unused variable warning in preflight steps
  ([`bcd38db`](https://github.com/nWave-ai/nwave-dev/commit/bcd38db4cbf029bd587864a0fc5ae8602036e5a1))

- **luna**: Add journey-sketch template and simplify dependencies
  ([`b0d309b`](https://github.com/nWave-ai/nwave-dev/commit/b0d309b2d2157fcd56f7fa0e5a4c52dc0b931aa1))

- **nwave**: Add CRITICAL INVARIANT gate to prevent incomplete finalize
  ([`44117d3`](https://github.com/nWave-ai/nwave-dev/commit/44117d35a20ac29c76e0ef7900eb6b0b332b6498))

- **nwave**: Address critical review findings - dynamic URLs and complete plugin chain
  ([`5984fb1`](https://github.com/nWave-ai/nwave-dev/commit/5984fb1c6e45f2323884f830bf7f5c4c8b63417b))

- **nwave**: Address DoR review findings for version update requirements
  ([`1ba3d2f`](https://github.com/nWave-ai/nwave-dev/commit/1ba3d2f79e46be29f6c1ad7d84becf281498387a))

- **nwave**: Apply ruff-format to validate_steps_complete.py for CI/CD compliance
  ([`e83ccab`](https://github.com/nWave-ai/nwave-dev/commit/e83ccabb6101705d00d0aeb65d8a35652f472c88))

- **orchestrator**: Add missing return in _generate_des_markers
  ([`8710a74`](https://github.com/nWave-ai/nwave-dev/commit/8710a74755f7bdabf16d671fe6a74f488ac8b9c7))

- **pre-commit**: Exclude JSON files from ruff linter
  ([`173fd2b`](https://github.com/nWave-ai/nwave-dev/commit/173fd2b2bea5068c3e7591511df635e044a4c7ba))

- **quality-gates**: Enforce pre-commit testing and fix audit logger bugs
  ([`0531252`](https://github.com/nWave-ai/nwave-dev/commit/0531252916daa74f8f04252a8534238d28f12578))

- **release**: All commit types trigger patch version bump
  ([`993205a`](https://github.com/nWave-ai/nwave-dev/commit/993205a5842b1ba44feb1af7d794c54cc57a2e81))

- **release**: Revert non-functional commits to no release
  ([`d89f5e3`](https://github.com/nWave-ai/nwave-dev/commit/d89f5e3dffaa085548c43894b7ff6f596ffddea5))

- **release-readiness**: Support modern wheel metadata formats
  ([`45c15e5`](https://github.com/nWave-ai/nwave-dev/commit/45c15e51cf4f71cfbd5841248ce10ac9aa59c0bf))

- **schema**: Complete 8-phase TDD migration - update validators and tests
  ([`47e23de`](https://github.com/nWave-ai/nwave-dev/commit/47e23deb680fab8a181e6914ff90e44ed870721e))

- **slack**: Fix timestamp formatting + trigger GREEN notification
  ([`2f1b76f`](https://github.com/nWave-ai/nwave-dev/commit/2f1b76fb21515005c8b83e3e0c6781d2e3b8de52))

- **slack**: Update real Slack user IDs + trigger GREEN notification
  ([`bd34a6e`](https://github.com/nWave-ai/nwave-dev/commit/bd34a6e126b07bb5d886f29bbc5c49ea0f9409cf))

- **templates,des-us005**: Update step-template to use 8-phase TDD schema v2.0
  ([`bdccf20`](https://github.com/nWave-ai/nwave-dev/commit/bdccf20875e4739c1a1e75e096f3fea7ee81b1b5))

- **test**: Add tmp_path fixture to update service test
  ([`d38305f`](https://github.com/nWave-ai/nwave-dev/commit/d38305fda5d388360a4b38bcb161e4afa6cd9118))

- **test**: Correct essential commands expectations in verifier tests
  ([`fa0afa2`](https://github.com/nWave-ai/nwave-dev/commit/fa0afa225900c1454a19168c82f0bd3a7b8b0444))

- **test**: Fix 3 failing timeout monitoring tests by inlining step file creation
  ([`01677df`](https://github.com/nWave-ai/nwave-dev/commit/01677dfc23cbed564b1097bd7a71538325fa9fa0))

- **test**: Fix test_real_hook_audit and test_install_des_hooks
  ([`5012391`](https://github.com/nWave-ai/nwave-dev/commit/501239146f989a374763ee9e231a902f79b69e74))

- **test**: Fix test_real_hook_audit.py mock and assertions
  ([`aa2e910`](https://github.com/nWave-ai/nwave-dev/commit/aa2e91083d4fb33bea4c5819005d795b0d31e556))

- **test**: Mock CI environment and schema validation in tests
  ([`b318657`](https://github.com/nWave-ai/nwave-dev/commit/b318657868ef451318fc2de960c2e01e5fc71ff2))

- **test**: Mock Colors class for Windows CI compatibility
  ([`14ca9a2`](https://github.com/nWave-ai/nwave-dev/commit/14ca9a2c551e1e6b4ed120e7e4b1017a7ffd85b7))

- **test**: Use valid variable names in template validation test
  ([`8582bd1`](https://github.com/nWave-ai/nwave-dev/commit/8582bd1531fa6ac9fbd38d84b65e8cdd5e8222f8))

- **tests**: Align bug-1 hook tests with current plugin interface
  ([`8977dff`](https://github.com/nWave-ai/nwave-dev/commit/8977dff8584969b148e6be0f3a749a77c3b07c79))

- **tests**: Align stale test data with current DES implementation
  ([`1208196`](https://github.com/nWave-ai/nwave-dev/commit/12081969ac2166d2124ab60235642a3dcfa54909))

- **tests**: Create minimal_step_file fixture content
  ([`6453533`](https://github.com/nWave-ai/nwave-dev/commit/645353304de9f53750d4db838b9747d49e2fb3c2))

- **tests**: Cross-platform compatibility for Windows CI
  ([`51313e7`](https://github.com/nWave-ai/nwave-dev/commit/51313e78d6ec3569fd27af50edb8e125cf9bcbfa))

- **tests**: Fix remaining test failures after bug fixes
  ([`9440e91`](https://github.com/nWave-ai/nwave-dev/commit/9440e910543c7ff1a54c20d2af02241a0011f65f))

- **tests**: Handle stderr not separately captured in CleanCliRunner
  ([`59515d8`](https://github.com/nWave-ai/nwave-dev/commit/59515d8b13405e6c3c4fedf8375068dc1e6eedf0))

- **tests**: Inherit system environment for Windows subprocess
  ([`67556a1`](https://github.com/nWave-ai/nwave-dev/commit/67556a127c074989b8aa33737531bef36f6bf418))

- **tests**: Preserve PATH in pre-push test environment
  ([`c6e9af5`](https://github.com/nWave-ai/nwave-dev/commit/c6e9af5a86a9e3d58a2f88508089c29cc1d0fc53))

- **tests**: Replace empty pass statements with real assertions
  ([`f683c54`](https://github.com/nWave-ai/nwave-dev/commit/f683c54b99940296738e309080c4379647820874))

- **tests**: Resolve all remaining test fixture errors
  ([`e4fd1c6`](https://github.com/nWave-ai/nwave-dev/commit/e4fd1c6f1e6530a5177c1750bf32e2b7761fcfd4))

- **tests**: Resolve all test isolation issues
  ([`e83460a`](https://github.com/nWave-ai/nwave-dev/commit/e83460a5c64d60fcf42ab82c7c8b753f90f5e856))

- **tests**: Resolve CI ANSI escape code assertion failures
  ([`ff9d8a2`](https://github.com/nWave-ai/nwave-dev/commit/ff9d8a23eb540c15f2dbf6da333887ed9690cb2b))

- **tests**: Resolve CI/CD test failures
  ([`385d7b2`](https://github.com/nWave-ai/nwave-dev/commit/385d7b2bb3313f40a62a24fa242d8453ac2fe5e3))

- **tests**: Resolve local quality gate failures
  ([`e122a29`](https://github.com/nWave-ai/nwave-dev/commit/e122a2998329c768ccacebd496bd8134cef87f97))

- **tests**: Resolve remaining CI test failures
  ([`4a0ed3e`](https://github.com/nWave-ai/nwave-dev/commit/4a0ed3e1aa2f9ba9e85763c74e776cd283fa4cda))

- **tests**: Resolve test collection errors
  ([`8d298df`](https://github.com/nWave-ai/nwave-dev/commit/8d298df5d8dd8e87b312abfeac243ba68e730619))

- **tests**: Skip Unix permission test on Windows
  ([`60902e0`](https://github.com/nWave-ai/nwave-dev/commit/60902e06666804401fbf50719e117a5f79600da4))

- **tests**: Use sys.executable for Windows compatibility in pre-push tests
  ([`110c9fd`](https://github.com/nWave-ai/nwave-dev/commit/110c9fd69c86ad83c4ebdb8ef2928ba9d24b9296))

- **tui**: Resolve test marker collision, add duration, align patterns
  ([`adc6a94`](https://github.com/nWave-ai/nwave-dev/commit/adc6a94996d9461063235296ee4108153e501a4a))

- **validation**: Count only files with valid extensions, exclude directories
  ([`9260285`](https://github.com/nWave-ai/nwave-dev/commit/92602850db91f57a7dfd806b79763fa5470c68ff))

- **windows**: Resolve path separator compatibility for cross-platform CI
  ([`f079ea2`](https://github.com/nWave-ai/nwave-dev/commit/f079ea24d2b89b18416346379e9d064a857eb8cc))

### Features

- Add DISCOVER wave as first phase in 6-wave nWave framework
  ([`8bb59ae`](https://github.com/nWave-ai/nwave-dev/commit/8bb59ae51b9109865aaa552d9255f8e9e3abf21e))

- Add documentation freshness check to pre-commit hooks
  ([`5b39a3a`](https://github.com/nWave-ai/nwave-dev/commit/5b39a3a054a95166927b53fc8d5cd3c27d306d23))

- New agent Apex
  ([`1ca8df8`](https://github.com/nWave-ai/nwave-dev/commit/1ca8df83ef05cafc4afa4bdaa5b341aa1f2b5799))

- New python installation into a venv, discuss to develop:split
  ([`3b00d16`](https://github.com/nWave-ai/nwave-dev/commit/3b00d16a7f42804e3bdc0731639509800fb8c100))

- **00-01**: Done - walking skeleton complete
  ([`9668d1d`](https://github.com/nWave-ai/nwave-dev/commit/9668d1debb18f81501b33a0e90a065337e9224ba))

- **00-01**: Green - minimal stub adapter
  ([`164619d`](https://github.com/nWave-ai/nwave-dev/commit/164619dc84ac9a201fc494814ca1befa27f18296))

- **01-01**: Green - stale execution value object implementation
  ([`59e2335`](https://github.com/nWave-ai/nwave-dev/commit/59e2335cf112f5c5d3888bbc2aba7dd23b56e1ab))

- **01-02**: Create staleDetectionResult entity
  ([`7294b25`](https://github.com/nWave-ai/nwave-dev/commit/7294b25b4041d0bd31d5002cb3b50260821b845b))

- **01-02**: Done - orchestrator audit logging complete
  ([`d898954`](https://github.com/nWave-ai/nwave-dev/commit/d898954b85382f91e8d9d21abcc14f6521d32dfd))

- **01-02**: Green - staleDetectionResult entity implemented
  ([`e6f9a90`](https://github.com/nWave-ai/nwave-dev/commit/e6f9a90d3dd261bfae1c73936f85dd80e10be07b))

- **01-03**: Audit logging tests pass - step complete
  ([`802db8a`](https://github.com/nWave-ai/nwave-dev/commit/802db8aa5a5a43d62cac267f7b37cd97931d321d))

- **02-01**: Create DES configuration infrastructure - step complete
  ([`8319194`](https://github.com/nWave-ai/nwave-dev/commit/83191941f8003f1d45b336a150c4ab52109a92db))

- **02-01**: Create StaleExecutionDetector service with threshold configuration
  ([`f787ad5`](https://github.com/nWave-ai/nwave-dev/commit/f787ad5c3feb072cc06595e0bac82db5292b730e))

- **02-02**: Create Claude Code hook adapter with Single Source of Truth - step complete
  ([`df29a71`](https://github.com/nWave-ai/nwave-dev/commit/df29a7182faebf88508b09ee64e02436526a6c44))

- **02-02**: Implement threshold logic and age calculation
  ([`32f092a`](https://github.com/nWave-ai/nwave-dev/commit/32f092ad3882c6c651f42a4097b7631451961ff9))

- **02-04**: Define DownloadPort interface
  ([`6081ff9`](https://github.com/nWave-ai/nwave-dev/commit/6081ff95059e684f62b332851402b3a49eeadc0e))

- **03-01**: Create hook installer with install/uninstall lifecycle - step complete
  ([`c962023`](https://github.com/nWave-ai/nwave-dev/commit/c962023a985610cb17b49c73035990db1515adb8))

- **03-04**: Complete DES orchestrator integration for recovery guidance with full 8-phase TDD
  execution
  ([`1fb220b`](https://github.com/nWave-ai/nwave-dev/commit/1fb220bad6e9a39120ac0f71e6d038be9e2f6087))

- **03-05**: Complete failure mode registry - all 7 modes with recovery guidance
  ([`7881ae4`](https://github.com/nWave-ai/nwave-dev/commit/7881ae438afda690068d8e293702cf701f776203))

- **acceptance**: Implement 4 high-priority scenarios for US-001 and US-002
  ([`06e8f52`](https://github.com/nWave-ai/nwave-dev/commit/06e8f5256690cfd03b2cf2d47a9f8021ff6ed8d1))

- **acceptance**: Implement US-002 permission and disk space scenarios
  ([`8d2ca1e`](https://github.com/nWave-ai/nwave-dev/commit/8d2ca1edf46867e2ccaabd293d85ebfecd6c64b7))

- **agents**: Add 3 design mandates for acceptance tests
  ([`27beb11`](https://github.com/nWave-ai/nwave-dev/commit/27beb11cced737c8288c4c637f1a60c7f8065041))

- **agents**: Add 5 test design mandates to software-crafter
  ([`b642fa9`](https://github.com/nWave-ai/nwave-dev/commit/b642fa91b2a23288e4e324b73c768b4eddcde720))

- **agents**: Add behavior-first test budget enforcement (G8)
  ([`3646d1b`](https://github.com/nWave-ai/nwave-dev/commit/3646d1bfbcb035ccadf3754e24e7923bc3c66789))

- **agents**: Add Luna (leanux-designer) and Eclipse (reviewer) UX team
  ([`8917b3e`](https://github.com/nWave-ai/nwave-dev/commit/8917b3e589a6ff89c301d375819fa85b0ed70ad0))

- **agents**: Add roadmap concision & precision mandate
  ([`7210132`](https://github.com/nWave-ai/nwave-dev/commit/72101321ce4db1d28684373c2368273b0781e9b0))

- **agents**: Add roadmap quality checks for implementation and tests
  ([`9ba1574`](https://github.com/nWave-ai/nwave-dev/commit/9ba15745768edc2b2b2d2c0fb199e674424b34b7))

- **agents**: Add software-crafter-light for A/B token comparison
  ([`460c733`](https://github.com/nWave-ai/nwave-dev/commit/460c733a273068491cee2eb12a76fd527cae83b5))

- **agents**: Promote heavy-clean software-crafter, clean embeddings
  ([`e56a5e5`](https://github.com/nWave-ai/nwave-dev/commit/e56a5e5a09a7664869935588c12115e0a70c14ba))

- **APEX-002**: Add DEVELOP wave baseline, roadmap, and step files
  ([`c5373da`](https://github.com/nWave-ai/nwave-dev/commit/c5373da2f54855bcc37d634c7a01e0261b4aebbf))

- **APEX-002**: Add installation environment detection feature planning
  ([`fa663b8`](https://github.com/nWave-ai/nwave-dev/commit/fa663b85daa6106d4953d0046614b9e022810f94))

- **APEX-002**: Add platform architecture and CI environment scenarios
  ([`2f8c091`](https://github.com/nWave-ai/nwave-dev/commit/2f8c09131fcddc376205fd62eb3bd7aedb181f44))

- **APEX-002**: Implement pre-flight environment detection for nWave installer
  ([`554157f`](https://github.com/nWave-ai/nwave-dev/commit/554157fb647d2441a05adb8349c2f42c3ccc834d))

- **audit**: Extract feature_name/step_id as direct PortAuditEvent fields in _log_audit_event
  ([`31e4a1b`](https://github.com/nWave-ai/nwave-dev/commit/31e4a1bea7eceab57207e5df27278ff949da9a4f))

- **audit-log**: Add feature_name and step_id fields to port-layer AuditEvent
  ([`fda0b9e`](https://github.com/nWave-ai/nwave-dev/commit/fda0b9ec7b3eaaff192605499202847dca54e4b0))

- **audit-log**: Verify AuditEvent dataclass refactoring complete (step 01-01)
  ([`9ce9fd9`](https://github.com/nWave-ai/nwave-dev/commit/9ce9fd9dd00360d7d8e10ca3949db41d6a598144))

- **audit-log-refactor/01-02**: Update read_entries_for_step() signature
  ([`891266f`](https://github.com/nWave-ai/nwave-dev/commit/891266fc8725cd24f029f9e2dc3d06fa731453fb))

- **backup**: Enable US-004 backup cleanup tests
  ([`09980a4`](https://github.com/nWave-ai/nwave-dev/commit/09980a4f370373d06e621b3960d76514bc7b4fe6))

- **backup**: Implement US-004 backup cleanup scenarios
  ([`33f2a54`](https://github.com/nWave-ai/nwave-dev/commit/33f2a54ec15dcc38dfc5c28a90a506b9ae9f4220))

- **breaking**: Remove split command - schema v2.0 migration complete
  ([`1e0f9c9`](https://github.com/nWave-ai/nwave-dev/commit/1e0f9c96624f6419fb028a992efe2b07600b4a78))

- **build**: Implement BUILD:INJECT support in command_processor
  ([`029d3d2`](https://github.com/nWave-ai/nwave-dev/commit/029d3d2423db4199493c5af2a326624fc4018f63))

- **changelog**: Implement US-007 changelog generation scenarios
  ([`e4fe037`](https://github.com/nWave-ai/nwave-dev/commit/e4fe03731f99a69892c3c29372bbbdfc47d7028b))

- **checkpoint**: Add CHECKPOINT_PENDING prefix for TDD checkpoint commits
  ([`3644b78`](https://github.com/nWave-ai/nwave-dev/commit/3644b78bf0fd116080fac081cad886c79f60b81a))

- **checkpoint**: Add CHECKPOINT_PENDING prefix for TDD checkpoint commits
  ([`0fc64b6`](https://github.com/nWave-ai/nwave-dev/commit/0fc64b6a32a4370be157d37c55d3445a8185fd5c))

- **ci**: Add commitlint to validate commit messages in CI
  ([`928c711`](https://github.com/nWave-ai/nwave-dev/commit/928c711378c64172657c44365e38f565920105db))

- **ci**: Add Windows cross-platform compatibility
  ([`2221a85`](https://github.com/nWave-ai/nwave-dev/commit/2221a85d50fbcf8f37842b2914cb6b27f64d354a))

- **ci**: Python-semantic-release single source of truth for versioning
  ([`54f5d6c`](https://github.com/nWave-ai/nwave-dev/commit/54f5d6ce116b44d077978b8e5b0248ff03b32757))

- **ci-cd**: Add Slack notifications for pipeline failures
  ([`30edb7b`](https://github.com/nWave-ai/nwave-dev/commit/30edb7ba937c0801eca3a2abcb09895fddbc4499))

- **cli**: Add progress spinner with phase updates during install
  ([`fcdd668`](https://github.com/nWave-ai/nwave-dev/commit/fcdd668d0434ab812b887d03ba20395dee3c6978))

- **command-processor**: Add strict template validation
  ([`3540f89`](https://github.com/nWave-ai/nwave-dev/commit/3540f89dcdc0cf99129a4d567f75b3ce1d39c2a4))

- **config**: Add timeout threshold configuration support
  ([`a525eaa`](https://github.com/nWave-ai/nwave-dev/commit/a525eaac5592d1777d720d15018cb833215af711))

- **des**: Add centralized config with max_turns default of 30
  ([`5da77ba`](https://github.com/nWave-ai/nwave-dev/commit/5da77ba1712570d98a466ad9cdbe9cee2eeed20e))

- **des**: Add DISTILL wave acceptance tests for US-002 through US-009
  ([`6aec638`](https://github.com/nWave-ai/nwave-dev/commit/6aec6387600445cb1f57c6c3935c17e6fc446bd0))

- **des**: Add error handling and edge cases to DESOrchestrator - step 04-02
  ([`e1351bc`](https://github.com/nWave-ai/nwave-dev/commit/e1351bc8cf5deea16ab1620daa12d10a49649b4d))

- **des**: Add installation/uninstallation requirements and architecture
  ([`1b07c9d`](https://github.com/nWave-ai/nwave-dev/commit/1b07c9d2c9850d5c3e9e72691d2e933c630334a8))

- **des**: Add Schema v2.0 input support to SubagentStop hook
  ([`03f1144`](https://github.com/nWave-ai/nwave-dev/commit/03f114461553294c9a6811b5ac7a92cd0353b9eb))

- **des**: Add virtual environment isolation to installation (v1.1)
  ([`5ab429e`](https://github.com/nWave-ai/nwave-dev/commit/5ab429e6b5b450727b804e590ddff436872e35a1))

- **des**: Add workflow_type field and safety gates for configuration tasks (v1.3)
  ([`f18411a`](https://github.com/nWave-ai/nwave-dev/commit/f18411a769956d8b9740c92fc1d53cf69e35baef))

- **des**: Complete DESIGN wave with architecture documentation
  ([`8e61a9d`](https://github.com/nWave-ai/nwave-dev/commit/8e61a9de2ddd167bf5569d0a3126dda2d0313bb2))

- **des**: Complete DISCUSS wave with requirements and UAT scenarios
  ([`7b7ba84`](https://github.com/nWave-ai/nwave-dev/commit/7b7ba84888c3cb5940e94c613a67f5c4a6abab23))

- **des**: Complete DISTILL wave with US-001 E2E acceptance tests
  ([`ed07fb4`](https://github.com/nWave-ai/nwave-dev/commit/ed07fb427173b866911673a7338a75ff100a0a05))

- **des**: Complete hexagonal architecture redesign for DES hooks
  ([`293c8da`](https://github.com/nWave-ai/nwave-dev/commit/293c8da6cd61777f765914f868f3550076f7c166))

- **des**: Complete hexagonal architecture restructuring with backward compatibility
  ([`7eeb0b7`](https://github.com/nWave-ai/nwave-dev/commit/7eeb0b7d92b3df2997b728953c15c9cb5fcc5969))

- **des**: Complete legacy cleanup - delete 5 legacy modules + 75 dead tests
  ([`b9662ed`](https://github.com/nWave-ai/nwave-dev/commit/b9662eda2dfe1ba0154c2953865bf30f05fe2aef))

- **des**: Complete step 01-02 TurnCounter implementation - 14 phases complete
  ([`1c5bf44`](https://github.com/nWave-ai/nwave-dev/commit/1c5bf444304f7cec8ee7da0c9e87df8831e9c5a2))

- **des**: Complete US-002 Template Validation (6/6 steps)
  ([`a8b98b2`](https://github.com/nWave-ai/nwave-dev/commit/a8b98b2e12fb2044aa0070d442e29255d9a3940c))

- **des**: Implement 8-phase TDD optimization with schema versioning and automatic rollback
  ([`b259d28`](https://github.com/nWave-ai/nwave-dev/commit/b259d281ba37fcd28a9219e0fb69345fb772ea8b))

- **des**: Implement daily audit log rotation
  ([`c8cac2b`](https://github.com/nWave-ai/nwave-dev/commit/c8cac2bac8673cec2e35f945c51ffd56bcd4ad56))

- **des**: Implement dataclass-based schema validation with single source of truth (v1.4)
  ([`3b8a6f2`](https://github.com/nWave-ai/nwave-dev/commit/3b8a6f2b78b5abeefe139a93001b7dee8d1d7e79))

- **des**: Implement des_orchestrator fixture - step 01-01
  ([`100da9b`](https://github.com/nWave-ai/nwave-dev/commit/100da9b169ff3d6c6faf8038931685a62ba40c17))

- **des**: Implement orchestrator notification via SubagentStop hook context injection
  ([`5ddf7fa`](https://github.com/nWave-ai/nwave-dev/commit/5ddf7fa9b64163c4d93dfdeddaf93d0be4668e10))

- **des**: Implement Schema v2.0 append-only execution-log format
  ([`a98bd4e`](https://github.com/nWave-ai/nwave-dev/commit/a98bd4ec22c08c3155c995e27b26ad4684c323f0))

- **des**: Implement Schema v2.0 append-only execution-log.yaml validation
  ([`05dd3ab`](https://github.com/nWave-ai/nwave-dev/commit/05dd3ab87bb03641bbc5b7cc50e501552bb78a83))

- **des**: Implement Schema v2.0 with TDDSchemaLoader and step_id refactoring
  ([`1b9ef35`](https://github.com/nWave-ai/nwave-dev/commit/1b9ef35aee0f31a854117c32b6683240535cad86))

- **des**: Implement step 01-02 serialization + expand e2e test plan
  ([`e198fd7`](https://github.com/nWave-ai/nwave-dev/commit/e198fd7228183fe9f972d6e986967552c2701b73))

- **des**: Implement TurnCounter component - step 01-02 GREEN state
  ([`96a0490`](https://github.com/nWave-ai/nwave-dev/commit/96a0490b2af24973e16aeb2fe629cf39bdf0d155))

- **des**: Implement two-tier DES validation (orchestrator vs execution)
  ([`2d195a8`](https://github.com/nWave-ai/nwave-dev/commit/2d195a867919d53e4ff71375631d06bc810b3a74))

- **des**: Integrate DES hook removal into uninstall script
  ([`9528188`](https://github.com/nWave-ai/nwave-dev/commit/9528188690d87dca9c72d4f3ea21d92a0af39a52))

- **des**: Integrate hooks into DES plugin with settings preservation
  ([`53fb30c`](https://github.com/nWave-ai/nwave-dev/commit/53fb30cf70f3e194069dc95cda4bf9a982bbb7f9))

- **des**: Redesign watchdog as session-scoped stale detection
  ([`31edda0`](https://github.com/nWave-ai/nwave-dev/commit/31edda02736b27df3b12f98bf9f4bc3ff1b25ed4))

- **des**: Restore claude_code_hook_adapter with Schema v2.0 + integration tests
  ([`0aa2459`](https://github.com/nWave-ai/nwave-dev/commit/0aa2459b136b82d12f9b261f0e843ddead7002ca))

- **des**: Save DES design session - checkpoint for conversation recovery
  ([`7ab93e6`](https://github.com/nWave-ai/nwave-dev/commit/7ab93e6ae578836f4ecb56ff9fcdb01b52b4098a))

- **des**: Step 03-02 render_prompt/validate_prompt use direct PortAuditEvent fields
  ([`3d4ddd3`](https://github.com/nWave-ai/nwave-dev/commit/3d4ddd3afd7c224fd04f6dc02aaf51d23aac712e))

- **des**: US-009 dual-layer DES enforcement (SubagentStop + PostToolUse)
  ([`a79aaef`](https://github.com/nWave-ai/nwave-dev/commit/a79aaef485b09599b7d4b37f576a5aff1438c48a))

- **des-01-01**: GREEN_ACCEPTANCE - des_orchestrator fixture with DES validation markers
  ([`153e51a`](https://github.com/nWave-ai/nwave-dev/commit/153e51a9bc0ab4f37a4934b5d6537b23ca607969))

- **des-hook-enforcement**: Add hook audit event types - step 01-01
  ([`a8a8aa2`](https://github.com/nWave-ai/nwave-dev/commit/a8a8aa2bcd4a3320c2e2acdf1ccb4971945d58c3))

- **des-us002**: Complete all 6 step executions with 14-phase TDD
  ([`6b8229a`](https://github.com/nWave-ai/nwave-dev/commit/6b8229a6df40613b8caa640087ad8ee0369640d4))

- **des-us002**: Finalize DEVELOP wave with mutation testing and evolution documentation
  ([`8ad03bf`](https://github.com/nWave-ai/nwave-dev/commit/8ad03bfb884e29dc8a55ee8714714e40acf2131d))

- **des-us002**: Implement DESMarkerValidator for prompt validation
  ([`ff638b7`](https://github.com/nWave-ai/nwave-dev/commit/ff638b7dde2a5a6645b1d91fb78d086cc58cbaf7))

- **des-us002**: Implement pre-invocation template validator
  ([`9e57137`](https://github.com/nWave-ai/nwave-dev/commit/9e5713774a5adde6030a3020b80f0ae43f7662a4))

- **des-us002**: Implement TDD phase detection with context-aware marker analysis
  ([`f37595a`](https://github.com/nWave-ai/nwave-dev/commit/f37595a353d2cc8498ad648d5f5a633072318d13))

- **des-us002**: Integrate TemplateValidator into DESOrchestrator entry point
  ([`3d3e226`](https://github.com/nWave-ai/nwave-dev/commit/3d3e226cad27fbab72fba3f2978e1bce74eb70a7))

- **des-us003**: AC-003.4 - Flag EXECUTED phases without outcome
  ([`0174199`](https://github.com/nWave-ai/nwave-dev/commit/01741995fbccd56610aa732be6bc52d6feffb291))

- **des-us003**: Complete step 01-03 - silent completion detection
  ([`50bdc0a`](https://github.com/nWave-ai/nwave-dev/commit/50bdc0af32d308e88166988a42e92502935fbca7))

- **des-us003**: Enable happy path validation tests (step 01-07)
  ([`b57f983`](https://github.com/nWave-ai/nwave-dev/commit/b57f983df3a82483bf6573247e74ada59dab5f7b))

- **des-us003**: Finalize and archive - all 8 steps complete
  ([`d0e271a`](https://github.com/nWave-ai/nwave-dev/commit/d0e271a400a7c9ddc78dba415093772d809bbbca))

- **des-us003**: Implement INVALID_SKIP detection in SubagentStopHook (step 01-05)
  ([`a6fcfe4`](https://github.com/nWave-ai/nwave-dev/commit/a6fcfe4516ffdd31e6dc5956aca0234de2fde1dd))

- **des-us003**: Implement multiple error aggregation with recovery suggestions (AC-003.6)
  ([`c4b4aaa`](https://github.com/nWave-ai/nwave-dev/commit/c4b4aaa678fc79795e911c6f0b1f960654858302))

- **des-us003**: Implement silent completion detection (step 01-03)
  ([`fb0865b`](https://github.com/nWave-ai/nwave-dev/commit/fb0865b36bd42dc2d183c25d6cd7d71aa950aae7))

- **des-us003**: Step 01-01 complete - SubagentStopHook implementation with 14-phase TDD
  ([`7fba0f0`](https://github.com/nWave-ai/nwave-dev/commit/7fba0f0bc6198cf8431031af959ba4bdb7fb02e1))

- **des-us004**: Add comprehensive TurnCounter tests with edge cases and serialization
  ([`70305a5`](https://github.com/nWave-ai/nwave-dev/commit/70305a57777960073c4449e7fd488c11c5f1fe6f))

- **des-us004**: Add ConfigLoader with turn limits by task type
  ([`8077dd1`](https://github.com/nWave-ai/nwave-dev/commit/8077dd12c1eb235a2458ce066ea87293cac4a852))

- **des-us004**: Add configurable turn limits per task type - step 01-03
  ([`421050e`](https://github.com/nWave-ai/nwave-dev/commit/421050e7d75b7be48e1fc88d2564f02715ac08f1))

- **des-us004**: Add duration_seconds to step schema for fine-grained tracking
  ([`3724374`](https://github.com/nWave-ai/nwave-dev/commit/3724374109ae8d93b7d7fb047cfcb0abf8814863))

- **des-us004**: Add extensions_granted field to step schema
  ([`62b8ee4`](https://github.com/nWave-ai/nwave-dev/commit/62b8ee46d361c192578cf7cb9f02ad24eda205d0))

- **des-us004**: Add request_extension method to DESOrchestrator - step 06-01
  ([`83f24bd`](https://github.com/nWave-ai/nwave-dev/commit/83f24bd2d751a3fa3a82b359135c0dde18faf22e))

- **des-us004**: Add timeout warning to agent prompt context (04-02)
  ([`c0378bc`](https://github.com/nWave-ai/nwave-dev/commit/c0378bc021a3769bb35e7aa3764fff23c111b72c))

- **des-us004**: Complete Step 01-01 - 14-phase TDD cycle for AuditLogger append-only implementation
  ([`6706406`](https://github.com/nWave-ai/nwave-dev/commit/6706406ad0b6bf4589df3f1bfdb2f36ec62eca21))

- **des-us004**: Complete step 01-03 - ConfigLoader with turn limits
  ([`dc30cd8`](https://github.com/nWave-ai/nwave-dev/commit/dc30cd85665b72494b51b07e93aa2c6987b405d8))

- **des-us004**: Complete step 05-02 - ExtensionApprovalEngine (COMMIT/PASS)
  ([`d23601d`](https://github.com/nWave-ai/nwave-dev/commit/d23601daef963b4e3da1f5494af208f7889ebafc))

- **des-us004**: Complete step 05-03 - extension tracking schema
  ([`65b3e70`](https://github.com/nWave-ai/nwave-dev/commit/65b3e70a072e56279a3b3b34bd934d0ad15ce517))

- **des-us004**: Design extension request API - step 05-01
  ([`86d31b6`](https://github.com/nWave-ai/nwave-dev/commit/86d31b641de481d849476a50925a1d75fc69dcc2))

- **des-us004**: Document completion of TimeoutMonitor unit tests (step 09-02)
  ([`4ef3cf1`](https://github.com/nWave-ai/nwave-dev/commit/4ef3cf13fa5bb9284c2dcbd0c8842319f788cc35))

- **des-us004**: Extend step schema with turn_count field - step 01-01
  ([`697e5db`](https://github.com/nWave-ai/nwave-dev/commit/697e5db66a8fe3385dba8d5a63c6c0c7c1d81f29))

- **des-us004**: GREEN_ACCEPTANCE - all tests passing for step 02-01
  ([`09deffd`](https://github.com/nWave-ai/nwave-dev/commit/09deffd461eb88f9104accb8e1dcf41edf9f2c84))

- **des-us004**: Implement execute_step() with TurnCounter integration - step 02-01 GREEN_UNIT
  ([`7dc534d`](https://github.com/nWave-ai/nwave-dev/commit/7dc534d2bae686e149d107fbd71f804f7a84cddc))

- **des-us004**: Implement ExtensionApprovalEngine (step 05-02 GREEN_UNIT)
  ([`2bdc16d`](https://github.com/nWave-ai/nwave-dev/commit/2bdc16d1b446efd9bf10ea6994019d6c1bb33931))

- **des-us004**: Implement request_extension method in DESOrchestrator - step 06-01
  ([`bfc2e0e`](https://github.com/nWave-ai/nwave-dev/commit/bfc2e0ecc04c2f864f84f89b47ec1531db2829d9))

- **des-us004**: Implement TimeoutMonitor component - step 03-02
  ([`3bfcc32`](https://github.com/nWave-ai/nwave-dev/commit/3bfcc324ef4778fc8fc8f8dcc4c457113fc923b0))

- **des-us004**: Wire TurnCounter into DESOrchestrator.execute_step() - step 02-01
  ([`7ec2b07`](https://github.com/nWave-ai/nwave-dev/commit/7ec2b07f797a3f95188b34a514ba23df528a55e7))

- **des-us004-03-02**: Implement TimeoutMonitor with elapsed time tracking
  ([`60d4d01`](https://github.com/nWave-ai/nwave-dev/commit/60d4d013bad99439e69348f5dbe1749bfd7f3390))

- **des-us004-04-01**: Wire TimeoutMonitor into orchestrator execution loop
  ([`598219e`](https://github.com/nWave-ai/nwave-dev/commit/598219e0cffcaf95c2893b028d72f072be785979))

- **des-us005**: Format recovery suggestions with junior-developer friendly language - step 03-02
  ([`b4158eb`](https://github.com/nWave-ai/nwave-dev/commit/b4158eb349890fd95854180ea54f21679f3eeece))

- **des-us005**: Implement AbandonedPhaseDetector for crash recovery - step 02-01
  ([`65c1aa4`](https://github.com/nWave-ai/nwave-dev/commit/65c1aa4ea9d8672c05b956af1b8d404890953ca4))

- **des-us005**: Implement step 01-02 - RecoveryGuidanceHandler core class with 8-phase TDD
  ([`59746e6`](https://github.com/nWave-ai/nwave-dev/commit/59746e684347d84d6ff9fa7518a48faaa04203a4))

- **des-us005**: Step 02-03 - Detect validation errors in step file structure
  ([`6440415`](https://github.com/nWave-ai/nwave-dev/commit/644041599815647fee42dda1b1ccea0597e8ec47))

- **des-us005**: Step 02-04 - Recovery guidance for stale execution and timeouts
  ([`c7f0591`](https://github.com/nWave-ai/nwave-dev/commit/c7f05919106118768e04a885fe05997c135d77a2))

- **des-us005-01-01**: Create recovery_suggestions data structure - 8-phase TDD cycle complete
  ([`e3cb2c0`](https://github.com/nWave-ai/nwave-dev/commit/e3cb2c01496884e78f9e3b5e7e0e016821092f35))

- **des-us005-02-05**: Detect invalid phase state transitions - step 02-05 complete
  ([`718f9d0`](https://github.com/nWave-ai/nwave-dev/commit/718f9d0c71e9d430b58b447dfac636bdd83064f2))

- **des-us005-03-01**: Enable and verify recovery suggestion actionable elements test
  ([`64c4173`](https://github.com/nWave-ai/nwave-dev/commit/64c41738b05a2aab58a5a8eb277cc95a17ebe9cb))

- **des-us005-03-03**: Complete 8-phase TDD cycle for validation error inline fix guidance
  ([`32a5b2e`](https://github.com/nWave-ai/nwave-dev/commit/32a5b2edad8794d5384a7f022b2426ddc74e9b63))

- **des-us005-03-04**: Integrate RecoveryGuidanceHandler with DES orchestrator
  ([`d938429`](https://github.com/nWave-ai/nwave-dev/commit/d93842933e5c488b04d4bdda2d3f771ec1a6e0e2))

- **des-us005/02-02**: Implement SilentCompletionDetector for silent completion detection
  ([`cc186a9`](https://github.com/nWave-ai/nwave-dev/commit/cc186a9ac44d58e5ae295943237e42fdfaed0747))

- **des-us006**: Add unit tests for _render_early_exit_protocol() - step 01-04
  ([`cac0f74`](https://github.com/nWave-ai/nwave-dev/commit/cac0f741f939d43cb6e89dcbb3818f1e0907a457))

- **des-us006**: Add unit tests for ad-hoc prompt behavior (step 02-03)
  ([`514ab9f`](https://github.com/nWave-ai/nwave-dev/commit/514ab9ffaf021c04615c7a89a6809c52b9f1e1cb))

- **des-us006**: Add unit tests for TIMEOUT_INSTRUCTION generation - step 02-01
  ([`6d4797e`](https://github.com/nWave-ai/nwave-dev/commit/6d4797e06d7e634b476509b96e060487ca70f107))

- **des-us006**: Complete step 01-02 - _render_turn_budget() validation
  ([`1945f1f`](https://github.com/nWave-ai/nwave-dev/commit/1945f1f199decc7e2b9a6ef77f7cd585c33f23e5))

- **des-us006**: Design TIMEOUT_INSTRUCTION template structure - step 01-01
  ([`79d3807`](https://github.com/nWave-ai/nwave-dev/commit/79d3807cc6ae04e9431ca3b206afccfc80c0d9d6))

- **des-us006**: Document step 01-05 - _render_turn_logging_instruction() already implemented
  ([`7cd803b`](https://github.com/nWave-ai/nwave-dev/commit/7cd803b5c8dd7e2821eb9134b8282539f75dabdf))

- **des-us006**: Enable test_scenario_003 progress checkpoints - step 01-03
  ([`2ebf4d4`](https://github.com/nWave-ai/nwave-dev/commit/2ebf4d4c886f996038cabc6f06ce61078a29cb39))

- **des-us006**: Validate 10/10 acceptance tests GREEN - step 05-01
  ([`91a2a2b`](https://github.com/nWave-ai/nwave-dev/commit/91a2a2b33571d5b6d3edf78b9cc90a66057f0926))

- **des-us006**: Validate baseline metrics achieved - step 05-02
  ([`283aa6f`](https://github.com/nWave-ai/nwave-dev/commit/283aa6f9589ca14718208f83bf37f9472ee3beab))

- **des-us006**: Verify /nw:research has no TIMEOUT_INSTRUCTION - step 02-04
  ([`77a9109`](https://github.com/nWave-ai/nwave-dev/commit/77a91097a021f474d0a10b1597e0ad5a480fea32))

- **des-us006**: Verify missing TIMEOUT_INSTRUCTION blocks invocation - step 03-01
  ([`afe457b`](https://github.com/nWave-ai/nwave-dev/commit/afe457b2e1068bd72ac7df1ab39ea93b7818c40a))

- **des-us006**: Verify orchestrator.py LOC within target (step 04-03)
  ([`09079e2`](https://github.com/nWave-ai/nwave-dev/commit/09079e25d243398f81104e170c05b2cf2fc09835))

- **des-us006-02-00**: Enable test_scenario_001 - render_full_prompt() entry point
  ([`2c41215`](https://github.com/nWave-ai/nwave-dev/commit/2c41215271229f4afa65bb3a3d398c205a728ff8))

- **des-us007**: Add CAPS emphasis and Marcus reference to continuation prohibition - step 02-04
  ([`fc6991e`](https://github.com/nWave-ai/nwave-dev/commit/fc6991eb7c2d865dc114214bcdb4c856776b676b))

- **des-us007**: Add implicit allowlist for step file modification - step 03-03
  ([`faaf794`](https://github.com/nWave-ai/nwave-dev/commit/faaf794a2268d110c9111cbf866c9e39f592f3af))

- **des-us007**: Add SCOPE_VIOLATION event type to AuditLogger - step 04-01
  ([`312792a`](https://github.com/nWave-ai/nwave-dev/commit/312792ab83a8b246fbdf13da79773cd77b0556ae))

- **des-us007**: Complete mutation testing with 94.12% score using Cosmic Ray
  ([`56a4839`](https://github.com/nWave-ai/nwave-dev/commit/56a4839fe5387b4bf7b691b466e4bf66a597ab13))

- **des-us007**: Create BoundaryRulesGenerator with orchestrator integration - step 02-01
  ([`d96eaf7`](https://github.com/nWave-ai/nwave-dev/commit/d96eaf733486c8db761ba2d5b9deb60e09838f39))

- **des-us007**: Create BoundaryRulesTemplate with section header rendering - step 01-01
  ([`cccc504`](https://github.com/nWave-ai/nwave-dev/commit/cccc504f7519e5c8b7fb05dd992ec0058e3070e0))

- **des-us007**: Create ScopeValidator with git diff integration and error handling - step 03-01
  ([`ef8610e`](https://github.com/nWave-ai/nwave-dev/commit/ef8610eb357146019e227c089ee81122b19d2bbf))

- **des-us007**: Enhance FORBIDDEN section with comprehensive scope prohibitions - step 02-03
  ([`0728cec`](https://github.com/nWave-ai/nwave-dev/commit/0728cec45be3ed931f43a69becc426818e53ac0f))

- **des-us007**: Finalize and archive project - all 16 steps complete
  ([`29b9339`](https://github.com/nWave-ai/nwave-dev/commit/29b93399c8cd09c3d1b23bcd37617e15881fad2d))

- **des-us007**: Implement glob pattern conversion for target_files - step 02-02
  ([`d5703c2`](https://github.com/nWave-ai/nwave-dev/commit/d5703c29d269afdd28d0d6836f10120dda24f3ff))

- **des-us007**: Implement token-minimal architecture (Schema v2.0)
  ([`1fa6c5c`](https://github.com/nWave-ai/nwave-dev/commit/1fa6c5c0a1cacfb941513cc291e8e49dbe7e3d37))

- **des-us007**: Integrate ScopeValidator violations with AuditLogger in SubagentStopHook - step
  04-02
  ([`4531094`](https://github.com/nWave-ai/nwave-dev/commit/453109444f833b7ac540acc8aecbba212112c441))

- **des-us007**: Integrate ScopeValidator with SubagentStopHook - step 03-04
  ([`a9c1e22`](https://github.com/nWave-ai/nwave-dev/commit/a9c1e226bfb99c0563b9b7a3905e03e84a21b2c5))

- **des-us007**: Validate clean executions produce no warning logs - step 04-04
  ([`ec1e15b`](https://github.com/nWave-ai/nwave-dev/commit/ec1e15b6afd41de36b724056b5042ec0eb43e579))

- **des-us007**: Validate in-scope file modifications pass validation - step 03-02
  ([`60f52df`](https://github.com/nWave-ai/nwave-dev/commit/60f52df8f433d0c3aad5a8845d23c8f6550b1840))

- **des-us007**: Validate multiple scope violations generate separate audit entries - step 04-03
  ([`639c2fa`](https://github.com/nWave-ai/nwave-dev/commit/639c2fabe82ae548aa4b6e9b2514b27b5d995c36))

- **des-us007**: Verify /nw:develop command includes BOUNDARY_RULES - step 01-03
  ([`3b75a11`](https://github.com/nWave-ai/nwave-dev/commit/3b75a11103cacacc413cf28a6d23bbd3dc643384))

- **des-us007-04-05**: Verify BOUNDARY_RULES validation blocks missing section - step 04-05
  ([`cb11f40`](https://github.com/nWave-ai/nwave-dev/commit/cb11f4063d7ebd976f07335a590ebe3b90014ea2))

- **des-us008**: Add metadata properties to document zero external dependencies
  ([`007e3e8`](https://github.com/nWave-ai/nwave-dev/commit/007e3e8a9140330cf03cb35c8c0c5de3ca7e118a))

- **des-us008**: Add pre-execution stale check to orchestrator - step 04-01
  ([`32f573e`](https://github.com/nWave-ai/nwave-dev/commit/32f573e4da66593d39c51eba5b316a30af0c22b8))

- **des-us008**: Create StaleResolver service to mark steps ABANDONED
  ([`f6b31d3`](https://github.com/nWave-ai/nwave-dev/commit/f6b31d3d750c6f7bef95c28397ed0af48a684e87))

- **des-us008**: Handle corrupted step files gracefully with warnings
  ([`0db7e5f`](https://github.com/nWave-ai/nwave-dev/commit/0db7e5f4b0ad141c978d34dbdadcd910808a8c12))

- **des-us008**: Support custom threshold via environment variable (step 02-03)
  ([`41b6e46`](https://github.com/nWave-ai/nwave-dev/commit/41b6e464e09ab3189207b9007bb2b72c224c698d))

- **des/us004**: Complete Audit Trail implementation with comprehensive tests
  ([`d62ae8d`](https://github.com/nWave-ai/nwave-dev/commit/d62ae8d7ef78522d9bdebe909273462c45b5b18d))

- **des/us005**: Orchestrate baseline, roadmap, and split phases for Failure Recovery
  ([`5c911f2`](https://github.com/nWave-ai/nwave-dev/commit/5c911f29a6614ccda7d14b044cb41609ac4b8f13))

- **design**: Add mandatory existing system analysis before designing
  ([`3e1bdec`](https://github.com/nWave-ai/nwave-dev/commit/3e1bdec4eef7048331de5ae21bdafad8381d616f))

- **design**: Add mandatory existing system analysis before designing
  ([`a9d0d5a`](https://github.com/nWave-ai/nwave-dev/commit/a9d0d5a8a8cf1501ae2161a5173fba3e33579df4))

- **design**: Complete DESIGN wave for versioning-release-management
  ([`ce184bb`](https://github.com/nWave-ai/nwave-dev/commit/ce184bbf042535daf749fbbe01cbe0220fc4128e))

- **develop**: Make mutation testing mandatory with Cosmic Ray as primary tool
  ([`8c0598a`](https://github.com/nWave-ai/nwave-dev/commit/8c0598a9e89a20bfff3a24ba1b4911271d2c3a9c))

- **distill**: Add bug testing directory structure and optional walking skeleton
  ([`5d536ce`](https://github.com/nWave-ai/nwave-dev/commit/5d536ce1e6b024896592d1dce512082ff2f85d17))

- **finalize**: Add documentation phase to finalization workflow
  ([`7c68b65`](https://github.com/nWave-ai/nwave-dev/commit/7c68b658ab473ab7014bfba5081980cf3d0c8786))

- **forge-build**: Add configurable spinners for wheel and IDE bundle build
  ([`1dbf990`](https://github.com/nWave-ai/nwave-dev/commit/1dbf990ee4e1055800a494f41c2978f86ede5a1e))

- **forge-build**: Add IDE bundle artifact summary to build complete
  ([`80a7acd`](https://github.com/nWave-ai/nwave-dev/commit/80a7acdc9a939bba185a2bb33d4b3dcd51ca2d75))

- **forge-install**: Add ASCII art branding to installation header
  ([`b89d74c`](https://github.com/nWave-ai/nwave-dev/commit/b89d74cbd81501342759bb202d4c7fe8e0ffc0d5))

- **forge-install**: Add asset deployment display section
  ([`0abf6f7`](https://github.com/nWave-ai/nwave-dev/commit/0abf6f79932ac0fc74850972d57a58e88c3aa5b5))

- **forge-install**: Add branded header at command start
  ([`059423d`](https://github.com/nWave-ai/nwave-dev/commit/059423d3f012a8affca12ddcc1a873cb3a999017))

- **forge-install**: Add CLI install section with spinner
  ([`6b20896`](https://github.com/nWave-ai/nwave-dev/commit/6b208962e1f7f032f7662926064312762d14e187))

- **forge-install**: Add deployment validation display section
  ([`1700013`](https://github.com/nWave-ai/nwave-dev/commit/170001310ca13c0aceae183e20a21d4b8718ad4d))

- **forge-install**: Add explicit validation error context
  ([`03c7375`](https://github.com/nWave-ai/nwave-dev/commit/03c73757e65bf056bc2ff652a3b8982d348c0875))

- **forge-install**: Remove header line and fix test marker ordering
  ([`5b3ffbc`](https://github.com/nWave-ai/nwave-dev/commit/5b3ffbcebbf4646ecaa2f1f16bc5b8336c17fcb5))

- **forge-install**: Update celebration to use nWave brand and add Getting started section
  ([`1660cd1`](https://github.com/nWave-ai/nwave-dev/commit/1660cd1a0b0cbc864494c529f70d9949d80c9a78))

- **forge-tui**: Add Phase 09 roadmap, integration architecture, and test pyramid
  ([`ab4ce1d`](https://github.com/nWave-ai/nwave-dev/commit/ab4ce1d12dd81a834add31fa97dcbc7832c77b03))

- **forge-tui**: Add TUI redesign acceptance plan and journey artifacts
  ([`214787c`](https://github.com/nWave-ai/nwave-dev/commit/214787ca80847abb8ee0bcaf3b7e608b7bf54fcd))

- **forge-tui**: Implement Phase 08 error handling for all failure scenarios
  ([`0294b2f`](https://github.com/nWave-ai/nwave-dev/commit/0294b2f5edc0628e4dd065d5faaec2444342a78b))

- **forge-tui**: Unify build + install TUI with IDE bundle and asset deployment
  ([`ec9ed09`](https://github.com/nWave-ai/nwave-dev/commit/ec9ed09f320713f207a0d31be3bf8af8aa028ea4))

- **forge-tui**: Wire IDE bundle build into forge_build CLI
  ([`387bcdc`](https://github.com/nWave-ai/nwave-dev/commit/387bcdcd5b816644a85e59ad0542110acf102b64))

- **git-workflow**: Implement commitlint validation hook
  ([`b581c2a`](https://github.com/nWave-ai/nwave-dev/commit/b581c2a57d909208eef6a5e2e184b8222258ff5e))

- **hooks**: Add subject case validation to commit-msg hook
  ([`e1e67dc`](https://github.com/nWave-ai/nwave-dev/commit/e1e67dca9d7c41b907513ec03c707b03bdece203))

- **hooks**: Enable US-006 pre-push validation tests
  ([`882222c`](https://github.com/nWave-ai/nwave-dev/commit/882222c69388660293836e66d7bbdb0c6aca0505))

- **hooks**: Implement US-006 VERSION file missing scenario
  ([`d984cef`](https://github.com/nWave-ai/nwave-dev/commit/d984cefe3853b38c86a8eaa614d9fecc15068ac2))

- **install**: Add Rich console library and replace Colors class
  ([`13cf509`](https://github.com/nWave-ai/nwave-dev/commit/13cf5098df7189e608c8a829a96960ffb08fc6c8))

- **install**: Add sys.path resolution for direct script execution
  ([`26c1bef`](https://github.com/nWave-ai/nwave-dev/commit/26c1beffd618e85b13276faef13d2a4125750b09))

- **installer**: Add ArtifactFlowValidator for consistency
  ([`ba5e477`](https://github.com/nWave-ai/nwave-dev/commit/ba5e47700ab07be7c66e237ae8282101535bb8e4))

- **installer**: Add integration checkpoint service
  ([`80e8d3b`](https://github.com/nWave-ai/nwave-dev/commit/80e8d3bcd96d3c7822ec542a83521aad7b0a40d4))

- **installer**: Add partial file cleanup to rollback service
  ([`e2fa15a`](https://github.com/nWave-ai/nwave-dev/commit/e2fa15a0998b6964bdd06a3e6de4de0bf2b9b21e))

- **installer**: Add PreflightFormatValidator for cross-journey consistency
  ([`a3610bd`](https://github.com/nWave-ai/nwave-dev/commit/a3610bd436d9eef6af7924ccd2a8d24743d38cba))

- **installer**: Add RollbackService for automatic and manual rollback - step 05-01
  ([`c513cd8`](https://github.com/nWave-ai/nwave-dev/commit/c513cd84953d1c03bbb9dbffd6bc2139ec59bc36))

- **installer**: Add SBOM dual-group format (CLI + IDE assets)
  ([`17a323c`](https://github.com/nWave-ai/nwave-dev/commit/17a323cafe37e687587d27f610b22a4c3541567b))

- **installer**: Add shared IDE bundle constants module
  ([`f605b2a`](https://github.com/nWave-ai/nwave-dev/commit/f605b2afa923fe17de6c7ece6fe0ffce68496e9f))

- **installer**: Add TestPyPI CI quality gate service - step 06-05
  ([`c4171c3`](https://github.com/nWave-ai/nwave-dev/commit/c4171c3ed1933a6bf7b3298641f98bd2be134b60))

- **installer**: Add TestPyPI E2E validation script and tests - step 06-04
  ([`226456c`](https://github.com/nWave-ai/nwave-dev/commit/226456c86df3ed7b64d3fc7ff7250f53cbc5eca9))

- **installer**: Extend InMemoryFileSystemAdapter with copy_file method
  ([`8f2812f`](https://github.com/nWave-ai/nwave-dev/commit/8f2812fc3c64487283c0aeb2b1392b7e23db201b))

- **installer**: Implement AssetDeploymentService with domain result class
  ([`ca69d69`](https://github.com/nWave-ai/nwave-dev/commit/ca69d69b0aaeac8afdec6943e994bfed3e81d4ce))

- **installer**: Implement DeploymentValidationService with domain result
  ([`685dc96`](https://github.com/nWave-ai/nwave-dev/commit/685dc96b7e233818b3e6d7885cc586e492a6500e))

- **installer**: Implement IdeBundleBuildService with domain result class
  ([`ebe19b2`](https://github.com/nWave-ai/nwave-dev/commit/ebe19b22dd6de49d2427207606868995160445cd))

- **installer**: Implement IdeBundleExistsCheck pre-flight check
  ([`f04a26b`](https://github.com/nWave-ai/nwave-dev/commit/f04a26b1c459c08cb57dd039766c95e30ddc47e7))

- **installer**: Improve health check with diagnostic flow and version display
  ([`752c9d0`](https://github.com/nWave-ai/nwave-dev/commit/752c9d086506078930205b6815b1d761ff0e0ca0))

- **installer**: Integrate deployment services into InstallService
  ([`4a10cb5`](https://github.com/nWave-ai/nwave-dev/commit/4a10cb59cbeaebf34e7b0f56ae7eb89e699a8411))

- **installer**: Integrate IdeBundleBuildService into BuildService with real integration tests
  ([`ca2f484`](https://github.com/nWave-ai/nwave-dev/commit/ca2f484151b47ac4579362aa145894791bd1f5b8))

- **installer**: Integrate upgrade detection into InstallService - step 05-04
  ([`5b208a2`](https://github.com/nWave-ai/nwave-dev/commit/5b208a23778e761509f6f31c0eeda32e8bbb3a88))

- **installer**: Replace build_framework TUI and parameterize spinner
  ([`19ad115`](https://github.com/nWave-ai/nwave-dev/commit/19ad1159d4477fc9236f660752148b68f7ef3897))

- **installer**: Replace check_source output with TUI emoji format
  ([`ecdef69`](https://github.com/nWave-ai/nwave-dev/commit/ecdef69abda2cb6cc7b49dcb5a27e1d6ba6e3ab8))

- **installer**: Replace header and preflight with Luna TUI format
  ([`1ec3483`](https://github.com/nWave-ai/nwave-dev/commit/1ec3483247b176ec5844f8a1c279d068f64365d4))

- **modern-cli-installer**: Activate E2E walking skeleton - step 04-09
  ([`621a444`](https://github.com/nWave-ai/nwave-dev/commit/621a4440df16dea88b1f244dbb2f830fe02fc130))

- **modern-cli-installer**: Add auto-chain build - step 03-08
  ([`8539e9e`](https://github.com/nWave-ai/nwave-dev/commit/8539e9ea3b4a7de2f9458acd5d756e1fa7ddc781))

- **modern-cli-installer**: Add BackupPort and BackupAdapter - step 03-04
  ([`e2f66e6`](https://github.com/nWave-ai/nwave-dev/commit/e2f66e69f3b9f3d81b56bf1fcf8ec07576a09e16))

- **modern-cli-installer**: Add forge:install CLI command - step 03-07
  ([`39293a3`](https://github.com/nWave-ai/nwave-dev/commit/39293a3a45ed590aed757e61c690c444ac196a70))

- **modern-cli-installer**: Add install-specific pre-flight checks - step 03-01
  ([`a883b5a`](https://github.com/nWave-ai/nwave-dev/commit/a883b5a4c94b47ae62f1850df5df0b903388e7f2))

- **modern-cli-installer**: Add InstallService core orchestration - step 03-05a
  ([`ff0cc36`](https://github.com/nWave-ai/nwave-dev/commit/ff0cc3637a4b8ceb7a40502f6b10e730ffc14caa))

- **modern-cli-installer**: Add InstallService verification phase - step 03-05b
  ([`7ffd442`](https://github.com/nWave-ai/nwave-dev/commit/7ffd4423fbc4be6795ae6bd0bef8d15be8368821))

- **modern-cli-installer**: Add PipxPort and PipxAdapter - step 03-02
  ([`7363ea4`](https://github.com/nWave-ai/nwave-dev/commit/7363ea4b32ec9c49a8ff0f71124c39808bfe1fc8))

- **modern-cli-installer**: Add release readiness validation - step 03-03
  ([`7214159`](https://github.com/nWave-ai/nwave-dev/commit/7214159628b980163fcbf474305f24223d4fa106))

- **modern-cli-installer**: Add release report generator - step 03-06
  ([`1de97b1`](https://github.com/nWave-ai/nwave-dev/commit/1de97b1af884c2dd666a19182b7a085de9e6d79c))

- **modern-cli-installer**: Add wheel selection prompt - step 03-09
  ([`fb4bfa6`](https://github.com/nWave-ai/nwave-dev/commit/fb4bfa61d180bdba542f0b924f4248597ce0d52c))

- **modern-cli-installer**: Create install-nwave CI mode support
  ([`2df061f`](https://github.com/nWave-ai/nwave-dev/commit/2df061f0f75073e21354b84f5c8f9264d52aeb53))

- **modern-cli-installer**: Create nw doctor CLI command - step 04-06
  ([`9ebc5d6`](https://github.com/nWave-ai/nwave-dev/commit/9ebc5d62fe44ed473590b553e49366cb7c98c044))

- **modern-cli-installer**: Create nw rollback CLI command - step 05-02
  ([`3bd8a10`](https://github.com/nWave-ai/nwave-dev/commit/3bd8a1023fb37dfc52531717c54d8d71f65dc778))

- **modern-cli-installer**: Create nw version command - step 04-07
  ([`e53ec72`](https://github.com/nWave-ai/nwave-dev/commit/e53ec7242319515b4d42d2b32e4507b23f701a24))

- **modern-cli-installer**: Create progress display service - step 04-03
  ([`d175f65`](https://github.com/nWave-ai/nwave-dev/commit/d175f654aa1aaf96e6e16a552fdb27fe3b089044))

- **modern-cli-installer**: Create PyPI-specific pre-flight checks - step 04-01
  ([`6184a51`](https://github.com/nWave-ai/nwave-dev/commit/6184a51a3e0c8b1882881bdcc60a5a88f36f97c0))

- **modern-cli-installer**: Create welcome and celebration display
  ([`f21fa30`](https://github.com/nWave-ai/nwave-dev/commit/f21fa3099e0e947da06077e1b2446e4cc10a08c3))

- **modern-cli-installer**: Implement DoctorFormatValidator service - step 06-02
  ([`0cfb426`](https://github.com/nWave-ai/nwave-dev/commit/0cfb426ff7b24a7fd121ee94d7de913898b4be47))

- **modern-cli-installer**: Implement nw setup CLI command - step 04-05
  ([`dc005fc`](https://github.com/nWave-ai/nwave-dev/commit/dc005fc64b955e9ea4850e8f91052b1e506a75fc))

- **modern-cli-installer**: Implement phases 00-02 of build journey
  ([`a8c7113`](https://github.com/nWave-ai/nwave-dev/commit/a8c7113bafe90a536e49231417e4a81a6209006a))

- **modern-cli-installer**: Step 04-02 - create upgrade detection service
  ([`5fa5558`](https://github.com/nWave-ai/nwave-dev/commit/5fa55583966f537e4e7eeac44bbea2c144c269fc))

- **mutation**: Add feature-scoped mutation testing for 10-50x speed improvement
  ([`0715508`](https://github.com/nWave-ai/nwave-dev/commit/0715508d892b9c4de94769de2da41aa4847c2bd3))

- **mutation**: Switch to commit-based mutation testing for hexagonal architecture
  ([`3b61561`](https://github.com/nWave-ai/nwave-dev/commit/3b61561a49355438ef76d04b1e037882a2c8e0a7))

- **mutation**: Switch to per-feature mutation testing (outside-in TDD)
  ([`00095cf`](https://github.com/nWave-ai/nwave-dev/commit/00095cf19492606548317450bf1be88b95d8f74f))

- **nwave**: Add /nw:update command for framework updates
  ([`4d505b6`](https://github.com/nWave-ai/nwave-dev/commit/4d505b644ea0d5797dbbb3658c91d9817ca9f88b))

- **nwave**: Add 5 countermeasures to prevent Testing Theatre
  ([`2d78502`](https://github.com/nWave-ai/nwave-dev/commit/2d78502efd2db514d439c2650d54b94075eb8c75))

- **nwave**: Add AGENT PROMPT REINFORCEMENT to command templates
  ([`60e15db`](https://github.com/nWave-ai/nwave-dev/commit/60e15db1501035ba5b41f6fd345ab5ec857c85c3))

- **nwave**: Add AGENT PROMPT REINFORCEMENT to command templates
  ([`ec6c36c`](https://github.com/nWave-ai/nwave-dev/commit/ec6c36c90636f4de29811decc01eed8c11c2410d))

- **nwave**: Add CRITICAL INVARIANT gate (STEP 4.5) to finalize command
  ([`4fdda27`](https://github.com/nWave-ai/nwave-dev/commit/4fdda270fff597ce77bbf170bd8d8a04ae175482))

- **nwave**: Add decision gates to TDD phases
  ([`7b68580`](https://github.com/nWave-ai/nwave-dev/commit/7b68580086be38f571ae5621977d4f659b02613c))

- **nwave**: Add roadmap quality gates to reduce over-decomposition and token waste
  ([`7fa59c5`](https://github.com/nWave-ai/nwave-dev/commit/7fa59c5c447173035af3307c6835643e9735f7b7))

- **nwave**: Add step-to-scenario mapping constraint for Outside-In TDD
  ([`8eab0c4`](https://github.com/nWave-ai/nwave-dev/commit/8eab0c4e5de3b7a3125e7d7ddea115acad22f0a7))

- **nwave**: Add step-to-scenario mapping constraint for Outside-In TDD
  ([`4877f75`](https://github.com/nWave-ai/nwave-dev/commit/4877f75b764048605c6050153ae4f9360b7d456b))

- **nwave**: Add version update experience requirements (DISCUSS wave)
  ([`8ee7909`](https://github.com/nWave-ai/nwave-dev/commit/8ee79097b2f51952440805e00eb32eee76f8cced))

- **nwave**: Prevent incomplete scope coverage in mutation testing quality gates
  ([`3f5b26e`](https://github.com/nWave-ai/nwave-dev/commit/3f5b26ee26890d0a102dccebac57b86ae065ef6f))

- **nwave**: Update wave commands to use feature-based folder structure
  ([`ce92605`](https://github.com/nWave-ai/nwave-dev/commit/ce92605eec6760199fb94c44565a63324af60038))

- **nwave**: Workflow improvements from US-008 retrospective (schema v3.0)
  ([`47d08ae`](https://github.com/nWave-ai/nwave-dev/commit/47d08aec51a54a82ea3a60782aba441b24d2c6e6))

- **phase-08**: Implement comprehensive error handling for forge TUI
  ([`cd5f536`](https://github.com/nWave-ai/nwave-dev/commit/cd5f5360c13eb79e2571efd37311495bac6f7e36))

- **plugin-arch**: Plugin infrastructure and wrapper plugins
  ([`d86acfa`](https://github.com/nWave-ai/nwave-dev/commit/d86acfaf2bc493d44100a64f474b891edc41782c))

- **plugin-architecture**: Add DES plugin prerequisite acceptance tests (step 03-01)
  ([`10d173c`](https://github.com/nWave-ai/nwave-dev/commit/10d173c6e8de94f061f3361d73224d07e26803f4))

- **plugin-architecture**: Behavioral equivalence validation (step 02-02)
  ([`4d0cc84`](https://github.com/nWave-ai/nwave-dev/commit/4d0cc844821cdf0ed6e0c679619d911a3ad4d7d8))

- **plugin-architecture**: DES import and script validation (step 03-03)
  ([`71fc750`](https://github.com/nWave-ai/nwave-dev/commit/71fc750e888b53fc3b503e00839b0e94134381b9))

- **plugin-architecture**: DESPlugin graceful failure handling (step 03-04)
  ([`3243035`](https://github.com/nWave-ai/nwave-dev/commit/324303539324f795dcba326fd4df8ea8b6ec5351))

- **plugin-architecture**: End-to-end user journey validation (step 05-02)
  ([`032cde5`](https://github.com/nWave-ai/nwave-dev/commit/032cde56ce5dbc58a015eaee10f34d4ec903e480))

- **plugin-architecture**: Implement CommandsPlugin wrapper (step 01-02)
  ([`794b05c`](https://github.com/nWave-ai/nwave-dev/commit/794b05ca3099e22c40ff2e17af8e0e2e6a3eeb5e))

- **plugin-architecture**: Implement DESPlugin with dependency resolution
  ([`452e2af`](https://github.com/nWave-ai/nwave-dev/commit/452e2af077b7bf7e028db77ef18c255d7d1dbfb5))

- **plugin-architecture**: Implement TemplatesPlugin wrapper (step 01-03)
  ([`87d794c`](https://github.com/nWave-ai/nwave-dev/commit/87d794c89ecf72da2be2f16456fa0b35f15ff4df))

- **plugin-architecture**: Implement UtilitiesPlugin wrapper (step 01-04)
  ([`5715d58`](https://github.com/nWave-ai/nwave-dev/commit/5715d58be8b8e779b8aaa2d240802f966a8a5a06))

- **plugin-architecture**: Selective installation and uninstallation (step 04-02)
  ([`cbd6c0b`](https://github.com/nWave-ai/nwave-dev/commit/cbd6c0b3959ebf8099a5e13ec3dda697888b8d07))

- **plugin-architecture**: Switchover install_framework() to PluginRegistry (step 02-01)
  ([`9118936`](https://github.com/nWave-ai/nwave-dev/commit/9118936e906853d2db756bc4881f6ff97a4d57d7))

- **plugin-architecture**: Upgrade scenario testing (step 04-03)
  ([`50e0118`](https://github.com/nWave-ai/nwave-dev/commit/50e0118959b3d326a50d4d65d8b775c697635096))

- **plugin-architecture**: Validate multi-plugin dependency resolution (step 01-05)
  ([`bfa111e`](https://github.com/nWave-ai/nwave-dev/commit/bfa111edd96baf4852d19c352d6f28c2721e8fdf))

- **plugin-architecture**: Walking Skeleton - AgentsPlugin E2E (step 01-01)
  ([`cc48737`](https://github.com/nWave-ai/nwave-dev/commit/cc487376ef1fc67307efdb7c6da9e7fa37cb2f39))

- **plugins**: Implement rollback mechanism for failed installations
  ([`60860ec`](https://github.com/nWave-ai/nwave-dev/commit/60860ecf0bc380cb2894635de94e63dee0fce589))

- **ports**: Define GitPort interface for git operations
  ([`d3afeb8`](https://github.com/nWave-ai/nwave-dev/commit/d3afeb810c6afc1e2bc92855fcd70906e52d980d))

- **refactoring**: Embed L1-L3 test refactoring guidance in software-crafter agent
  ([`2e612b6`](https://github.com/nWave-ai/nwave-dev/commit/2e612b62819788a1b8d4930fa7a5ed44f247a2cf))

- **schema**: Add turn_count field to phase_execution_log - Infrastructure step 01-01
  ([`a058d0c`](https://github.com/nWave-ai/nwave-dev/commit/a058d0c412379c2dec9b74924bb5e13470342b21))

- **slack**: Expand notifications to all branches + cleanup
  ([`a3babf4`](https://github.com/nWave-ai/nwave-dev/commit/a3babf42085f0bc22cdda725436e987903d25273))

- **templates**: Add concise baseline/roadmap/step templates with BUILD:INJECT
  ([`7191816`](https://github.com/nWave-ai/nwave-dev/commit/7191816c240e58046930e965461e538749ef3430))

- **tui**: Add version display, build spinner, wheel validation, and build complete emoji stream
  ([`7d67e1c`](https://github.com/nWave-ai/nwave-dev/commit/7d67e1c890841ea765ab1d962b002be0ebb5ae4b))

- **turn-counter-01-02**: Complete all 14 TDD phases for turn counter implementation
  ([`bbdff4b`](https://github.com/nWave-ai/nwave-dev/commit/bbdff4b2d0eb75c9c82122a1505a60ebe1e55c5d))

- **update**: Implement US-002 backup and update orchestration
  ([`e6b87b0`](https://github.com/nWave-ai/nwave-dev/commit/e6b87b0738e76747bda5872d4fb08f655d161745))

- **us-001**: Skip update check when watermark is fresh - step 03-05
  ([`83b7e81`](https://github.com/nWave-ai/nwave-dev/commit/83b7e8132e7b27a8d032a241e47a772b998c6e95))

- **us-003**: Implement forge build walking skeleton - step 05-01
  ([`eff00e2`](https://github.com/nWave-ai/nwave-dev/commit/eff00e25e83ed1db76e39d8f9e76954f5b5ce965))

- **us-004**: Implement forge:install walking skeleton - step 06-01
  ([`1aa26b4`](https://github.com/nWave-ai/nwave-dev/commit/1aa26b4aa690b4929d7b7e539bde87031a6cfb0c))

- **us001**: Handle missing VERSION file and rate limit gracefully
  ([`06cb95a`](https://github.com/nWave-ai/nwave-dev/commit/06cb95aeb86636866e29743fe5dd1d0ba525b3d9))

- **us001-03-02**: Display version when up-to-date
  ([`7cf360c`](https://github.com/nWave-ai/nwave-dev/commit/7cf360c896d4128a18323f2f05d1d657e97189f8))

- **us001-03-03**: Display version when offline with graceful error handling
  ([`c0ecf16`](https://github.com/nWave-ai/nwave-dev/commit/c0ecf164e720327b1520d9bd1f91f08fbd223e54))

- **us001-03-04**: Daily auto-check updates watermark when stale
  ([`e1afe85`](https://github.com/nWave-ai/nwave-dev/commit/e1afe85edca3889f45d44ddd3917e0d68f5158a6))

- **us002-04-01**: Implement update with backup creation - walking skeleton
  ([`6dc4fb5`](https://github.com/nWave-ai/nwave-dev/commit/6dc4fb5c7e45b06bbef2992c2a1f48b08aea0d4a))

- **us002-04-02**: Major version change requires confirmation
  ([`d3f8749`](https://github.com/nWave-ai/nwave-dev/commit/d3f87499c5bb0206591e6f186b8ae27b7fe8cc14))

- **us002-04-03**: Major version update proceeds with confirmation
  ([`aa240e1`](https://github.com/nWave-ai/nwave-dev/commit/aa240e19b36d0b47e5d324318f8cafc2b7ba386a))

- **us002-04-04**: Major version update cancelled with denial
  ([`9b48465`](https://github.com/nWave-ai/nwave-dev/commit/9b48465d0e93566c83ece0cc894608049f625079))

- **us002-04-05**: Local RC version triggers customization warning
  ([`3ddb1be`](https://github.com/nWave-ai/nwave-dev/commit/3ddb1bece7f364f168c404f1958d42e8cde0ddde))

- **us002-04-06**: Network failure during download leaves installation unchanged
  ([`affa8ad`](https://github.com/nWave-ai/nwave-dev/commit/affa8ad1e944761330d13acf3e4f4f071bc8c785))

- **us002-04-09**: Non-nWave user content is preserved during update
  ([`57d2226`](https://github.com/nWave-ai/nwave-dev/commit/57d2226bb8834f70a8722ae8c144a101effff2c8))

- **us003-05-03**: RC counter increments on same day builds
  ([`b14ee11`](https://github.com/nWave-ai/nwave-dev/commit/b14ee118db44c13d887a2ebf8a1aff3271d846bc))

- **us003-05-05**: Feature branch name included in RC version
  ([`8a7d9af`](https://github.com/nWave-ai/nwave-dev/commit/8a7d9af650e20b913b03099951797ab34a3226a5))

- **us004-06-04**: Installation fails when dist/ is missing required files
  ([`42cd98e`](https://github.com/nWave-ai/nwave-dev/commit/42cd98e562daf56c58ff87f05ef3fe9e4f1a12b5))

- **us004-06-05**: Smoke test failure reports error
  ([`9676a17`](https://github.com/nWave-ai/nwave-dev/commit/9676a17f4ea8c48f4dded14b921414ae5a77f9e7))

- **us005**: Implement core recovery infrastructure - Phase 1
  ([`2a5332e`](https://github.com/nWave-ai/nwave-dev/commit/2a5332e426dd3fd63cdff480ea7ee1e6a2632b40))

- **us005-01-02**: Implement RCVersion value object
  ([`eb12d9a`](https://github.com/nWave-ai/nwave-dev/commit/eb12d9a76f1fcd0b4243795092380fc6a038a911))

- **us005-01-03**: Implement Watermark entity
  ([`ba8c90f`](https://github.com/nWave-ai/nwave-dev/commit/ba8c90fdaf759644ca7e556815a9c89edf6f9135))

- **us005-01-03**: Turn count persistence infrastructure - 8-phase TDD complete
  ([`6b10a22`](https://github.com/nWave-ai/nwave-dev/commit/6b10a227988efcf3b21863ac56bced7c6ed9c131))

- **us005-02-02**: Detect silent completion failures with recovery guidance
  ([`2f4cec9`](https://github.com/nWave-ai/nwave-dev/commit/2f4cec923dd6f1088a53eba294eaa1fcf47b3b98))

- **us005-02-03**: Detect missing artifacts failures with recovery guidance
  ([`86443bd`](https://github.com/nWave-ai/nwave-dev/commit/86443bd269c989256338aa508a9770d5e3f425e7))

- **us005-03-01**: Format recovery suggestions with WHY + HOW + Actionable structure
  ([`c44a748`](https://github.com/nWave-ai/nwave-dev/commit/c44a7487f8bfcd396e879c517a423e37e27184c1))

- **us005-03-02**: Include transcript path in crash recovery suggestions
  ([`9a852a3`](https://github.com/nWave-ai/nwave-dev/commit/9a852a3ca9ec28bdf8493e8b8e9ead66cb17dd03))

- **us005-03-03**: Integrate recovery suggestions with validation error messages
  ([`9ed5607`](https://github.com/nWave-ai/nwave-dev/commit/9ed5607a11d582639d76879c349b869ce615bdc0))

- **us005-03-04**: Polish recovery suggestions with junior-dev friendly language
  ([`8222cc1`](https://github.com/nWave-ai/nwave-dev/commit/8222cc1e43c9471aeb4d752be2d41efde0f590ee))

- **us005-03-05**: All 8 TDD phases COMPLETE - Comprehensive test suite, 91% coverage, junior-dev
  ready
  ([`bd4a1ce`](https://github.com/nWave-ai/nwave-dev/commit/bd4a1cec2522190d2fc8b9547e7eee3143d3e6e2))

- **us005-03-05**: PHASE PREPARE - Identified active E2E test scenario 1 (crash recovery)
  ([`48e51a9`](https://github.com/nWave-ai/nwave-dev/commit/48e51a92e247b032bdc3823a97055d76cac8f546))

- **us005-03-05**: PHASES RED_UNIT, GREEN, REVIEW - Unit tests complete, 91% coverage, 41 tests
  passing
  ([`364b1bb`](https://github.com/nWave-ai/nwave-dev/commit/364b1bbe6b63f17cef36141f670c708e450bc3af))

- **us005-07**: User accepts install after successful build
  ([`a3e9ae1`](https://github.com/nWave-ai/nwave-dev/commit/a3e9ae1b364d12493ccb10f8188c35599c2323fb))

- **us005-07-01**: Implement forge:release walking skeleton - step 07-01
  ([`69ea95f`](https://github.com/nWave-ai/nwave-dev/commit/69ea95f692cb414351765c5ab1694d3c3c863608))

- **us005-07-02**: Add acceptance test for release command fails on main branch
  ([`a4207bd`](https://github.com/nWave-ai/nwave-dev/commit/a4207bd00df05d89814400fae0ac828b5db82a51))

- **us005-07-04**: Permission denied for non-admin user
  ([`d991794`](https://github.com/nWave-ai/nwave-dev/commit/d991794f79e3d5f57e17541a69724eddfb2a0b87))

- **us005-07-06**: Release shows pipeline status after PR creation
  ([`ba49e5e`](https://github.com/nWave-ai/nwave-dev/commit/ba49e5e362d5efe01ee2d68d9d124b0f70cb0a69))

- **version**: Implement VersionManager for local version checking
  ([`124a425`](https://github.com/nWave-ai/nwave-dev/commit/124a4254c6d460e3a6458817b0d5cd96eaaa2dbc))

- **version-update**: Add DESIGN and DISTILL wave artifacts for version update experience
  ([`775273f`](https://github.com/nWave-ai/nwave-dev/commit/775273f6bbd52e959e74d020e387ecf1b69f5eb5))

- **version-update**: Add unit test for scoped commit validation - step 01-02
  ([`eda6aa4`](https://github.com/nWave-ai/nwave-dev/commit/eda6aa411b4dc468237a1794e536df412b137c22))

- **version-update**: Enable breaking change commit test - step 01-03
  ([`6af7286`](https://github.com/nWave-ai/nwave-dev/commit/6af7286eb85a00695a96f6200493b4f08c82e854))

- **version-update**: Implement major version breaking change warning - step 03-01
  ([`83c508b`](https://github.com/nWave-ai/nwave-dev/commit/83c508b0b07f80cc958183ac22a31a68f63039c3))

- **version-update-experience**: Complete DEVELOP wave preparation
  ([`36d78f7`](https://github.com/nWave-ai/nwave-dev/commit/36d78f72226fd237dd970c5440f6b6d8e57f2c6a))

- **versioning**: Define FileSystemPort interface (step 02-02)
  ([`e15f151`](https://github.com/nWave-ai/nwave-dev/commit/e15f1516e0bfc25b5f18985f2ea92be1eb675790))

- **versioning**: Display version with update available - step 03-01
  ([`78ebaf4`](https://github.com/nWave-ai/nwave-dev/commit/78ebaf41cc6e024dc09974b5a0455068dc7484ac))

- **versioning**: Implement BackupPolicy domain service - step 01-04
  ([`8dacd4c`](https://github.com/nWave-ai/nwave-dev/commit/8dacd4c791371622ddd7dbf42ffd22179cc8fe84))

- **versioning**: Implement GitHubAPIPort interface - step 02-01
  ([`f396c9b`](https://github.com/nWave-ai/nwave-dev/commit/f396c9b9d779c2c8ec8fa137fb06d5d66f8b8895))

- **versioning**: Implement Version entity with semantic versioning - step 01-01
  ([`587f17f`](https://github.com/nWave-ai/nwave-dev/commit/587f17fa985f93990b85a21a449f32127709487b))

### Performance Improvements

- **tests**: Refactor max_turns tests to use direct calls
  ([`48b8b59`](https://github.com/nWave-ai/nwave-dev/commit/48b8b59f7e5db172ae57c6aaf582b514dcfcc413))

### Refactoring

- Eliminate all shell scripts and enforce Python-only policy
  ([`1ec09af`](https://github.com/nWave-ai/nwave-dev/commit/1ec09af025dca9578ff8b8af29b70a424a2892cd))

- Extend template processor and remove hardcoded phases from all commands
  ([`560a634`](https://github.com/nWave-ai/nwave-dev/commit/560a6342fba6cab39e8c56c8ffe4324c7ef49d05))

- Move feature workflow files to tests/feature for better organization
  ([`0bab7e2`](https://github.com/nWave-ai/nwave-dev/commit/0bab7e21d829d759ff67065a785f42f62c11b4a0))

- Move Task safety rules to global CLAUDE.md
  ([`bb0920d`](https://github.com/nWave-ai/nwave-dev/commit/bb0920de40f9fc66cb53e7c536954ddb3b3a5d45))

- Remove backward compatibility re-exports
  ([`739bd69`](https://github.com/nWave-ai/nwave-dev/commit/739bd69426401059073b8612c0df9439a342e584))

- Remove old crafter_ai.installer and nWave.core.versioning architecture
  ([`e410cce`](https://github.com/nWave-ai/nwave-dev/commit/e410cce538a6dea10be55a081d99821520d5c745))

- Replace hardcoded TDD phases with build-time template substitution
  ([`5a7eb9c`](https://github.com/nWave-ai/nwave-dev/commit/5a7eb9c4f207eac8d396d0da881b5c18f5d9e2a8))

- Require Python 3.11+ and eliminate legacy compatibility
  ([`6c70898`](https://github.com/nWave-ai/nwave-dev/commit/6c708989ae6bd838338604023aee9cc0612fb598))

- **01-01**: Continuous and l4 phases completed
  ([`5086ebe`](https://github.com/nWave-ai/nwave-dev/commit/5086ebe8d92b55a05bf93f228698e5da18395578))

- **01-02**: Continuous and L4 refactoring skipped (not applicable)
  ([`d31d953`](https://github.com/nWave-ai/nwave-dev/commit/d31d9536aa359709c0badc9481988b430e4e0335))

- **agents**: Align software-crafter testing strategy with port-to-port TDD
  ([`ce35d30`](https://github.com/nWave-ai/nwave-dev/commit/ce35d30a004da7271d76100e9097f4be862649cb))

- **agents**: Compress software-crafter header and PART 6
  ([`2a9f7b7`](https://github.com/nWave-ai/nwave-dev/commit/2a9f7b7099901b76ee51adac9147967d7c415c09))

- **agents**: Extract Mikado Method to dedicated agent
  ([`3ad187e`](https://github.com/nWave-ai/nwave-dev/commit/3ad187e87d079c4d0c1b32ea0770f8382231a3c0))

- **audit**: Consolidate nWave audit into DES audit logger
  ([`9f78bba`](https://github.com/nWave-ai/nwave-dev/commit/9f78bba1b216a002eff79091c9d8e3649c055fff))

- **ci**: Redesign pipeline with explicit parallel jobs
  ([`697698d`](https://github.com/nWave-ai/nwave-dev/commit/697698d7238601a5793da3497ce27a3ad0892a44))

- **des**: Clarify command-specific template validation (v1.1 → v1.2)
  ([`976dd12`](https://github.com/nWave-ai/nwave-dev/commit/976dd120b92fff1ee5a5c2e0eac6833c6b934af5))

- **des**: Complete hexagonal architecture restructuring
  ([`566e7b6`](https://github.com/nWave-ai/nwave-dev/commit/566e7b61edb9bb11cdb1eae8cdc8e08a01b306d0))

- **des**: Eliminate hardcoded phases in ValidationErrorDetector
  ([`6bb7515`](https://github.com/nWave-ai/nwave-dev/commit/6bb75155ab9fbe0c5f2bb7e825efa020f0e91eef))

- **des**: Eliminate hardcoded phases in validator, use schema loader
  ([`1bcfce1`](https://github.com/nWave-ai/nwave-dev/commit/1bcfce1ee0dcdef6ccaae857612b8977baf1d76c))

- **des**: Eliminate validator duplication - consolidate to TemplateValidator
  ([`6733990`](https://github.com/nWave-ai/nwave-dev/commit/67339904d4419e03d2c36a574729ce778d88b2c5))

- **des**: Extract command detection into _get_validation_level() method
  ([`241e0a5`](https://github.com/nWave-ai/nwave-dev/commit/241e0a59a0b359288c46231d3a385dbb88c84e4d))

- **des**: Remove backward compatibility shims, enforce pure hexagonal architecture
  ([`bb3420d`](https://github.com/nWave-ai/nwave-dev/commit/bb3420d36ca23f664d364b86aaf7ba7f8467764f))

- **des**: Reorganize docs by nWave wave structure
  ([`9f8ec0c`](https://github.com/nWave-ai/nwave-dev/commit/9f8ec0c00d39eca648aa1fabbbc3bab91a548620))

- **des**: Schema v2.0 - complete execution-status.yaml → execution-log.yaml migration
  ([`c8dca89`](https://github.com/nWave-ai/nwave-dev/commit/c8dca89e264f5b7bc174122600ed613f1644cabf))

- **des,us007**: Phases 1-3 - Token-minimal architecture migration
  ([`ee4e69d`](https://github.com/nWave-ai/nwave-dev/commit/ee4e69d31f1d9b461274ffbc759143d32133231b))

- **des-us004**: Remove Extension API - complete cleanup
  ([`f608978`](https://github.com/nWave-ai/nwave-dev/commit/f608978610ef6ab351832851807e3f75e4d0a073))

- **des-us006**: Extract common markdown formatting to _format_instruction_element()
  ([`5edb304`](https://github.com/nWave-ai/nwave-dev/commit/5edb304f5623c5f60866255e05439eb366410675))

- **des-us006**: Update all internal references from des-us004 to des-us006
  ([`0e33a33`](https://github.com/nWave-ai/nwave-dev/commit/0e33a33cdb10a4c943eb8b7b6a3b13b1aa9c9d09))

- **develop**: Ultra-aggressive prose reduction - 6.3% smaller
  ([`863c1c8`](https://github.com/nWave-ai/nwave-dev/commit/863c1c8ceb7a07c5264293568ed4ae8149125244))

- **execute**: Ultra-aggressive prose reduction - 26% smaller
  ([`c8359b5`](https://github.com/nWave-ai/nwave-dev/commit/c8359b53e82d99ee602f8583202480c2cc823029))

- **forge-install**: Update tagline to emphasize code assistant role
  ([`a24679d`](https://github.com/nWave-ai/nwave-dev/commit/a24679db026b6deb4f862f457d7dc40f529f83b2))

- **hooks**: Fix pytest-validation blocking commits and ruff exit-code issues
  ([`abd988d`](https://github.com/nWave-ai/nwave-dev/commit/abd988d5108e79cc979b393848fa14a1e68acc41))

- **hooks**: Move documentation freshness check to push phase
  ([`461136d`](https://github.com/nWave-ai/nwave-dev/commit/461136d5c9a24f98eb745250de3972286406bd8a))

- **installer**: Logger console outputs raw TUI format, convert prints to logger
  ([`e927ae8`](https://github.com/nWave-ai/nwave-dev/commit/e927ae832ddcaa6b65e0cbedc62a2ce7a55eb86d))

- **installer**: Merge dual loggers into unified Logger with Rich support
  ([`c4d176d`](https://github.com/nWave-ai/nwave-dev/commit/c4d176d0324ccfa6d7247a586c772723059db276))

- **installer**: Remove dead .sh build path from build_framework
  ([`721bb99`](https://github.com/nWave-ai/nwave-dev/commit/721bb997d3f209a7100406efd3dce29a2e61e5e9))

- **installer**: Reorganize output flow to reduce repetition
  ([`2b6079f`](https://github.com/nWave-ai/nwave-dev/commit/2b6079f7f388d742876eea6f07bedda48bc9c65b))

- **installer**: Replace count-based validation with source-vs-target file comparison
  ([`651079e`](https://github.com/nWave-ai/nwave-dev/commit/651079eee79f40b1fed547e67e6bccbd5104057f))

- **level-2**: Extract DES marker generation helper method
  ([`e7e755a`](https://github.com/nWave-ai/nwave-dev/commit/e7e755ac78400d9c78a370a5263e8953dbe9838c))

- **level-2**: Extract timeout warning formatting to shared helper
  ([`2a3765f`](https://github.com/nWave-ai/nwave-dev/commit/2a3765f3ef9c377b97cc9f1827beddab817e4e4a))

- **level-3**: Add method grouping comments to orchestrator
  ([`e7135be`](https://github.com/nWave-ai/nwave-dev/commit/e7135be994c8bd6f1da499b08cc3f365241cc364))

- **nwave**: Purge deprecated step JSON file references
  ([`6886d8b`](https://github.com/nWave-ai/nwave-dev/commit/6886d8bba6aa4677289bf81056a904162b11ef3a))

- **nwave**: Restructure personas as Creators vs Users
  ([`7a6e4cc`](https://github.com/nWave-ai/nwave-dev/commit/7a6e4cc11969bd43abdc10753e2fb9f1ee5098d3))

- **quality**: Comprehensive cleanup of tests and CI anti-patterns
  ([`6667498`](https://github.com/nWave-ai/nwave-dev/commit/6667498cbd377da9f7b105ba5e6a9e978edfb2e4))

- **split**: Ultra-aggressive prose reduction - 30.5% smaller
  ([`11c5671`](https://github.com/nWave-ai/nwave-dev/commit/11c56719d01be76225f92f7714ef5611943dda8d))

- **tests**: Reorganize acceptance tests per DISTILL convention
  ([`353be1b`](https://github.com/nWave-ai/nwave-dev/commit/353be1bd2dde78014ea0fbeb3f3a18eb9bf814ce))

- **tests**: Reorganize DES acceptance tests into tests/des/acceptance/
  ([`ce6bc1a`](https://github.com/nWave-ai/nwave-dev/commit/ce6bc1ade1d749393d62902c792b1ad5bff81c61))

- **tui**: Add build header and pre-flight emoji stream with call reorder
  ([`d86a5e5`](https://github.com/nWave-ai/nwave-dev/commit/d86a5e50b32f59c5201f373618cc18b68e7df44a))

- **tui**: Add install header and pre-flight emoji stream
  ([`d4a0368`](https://github.com/nWave-ai/nwave-dev/commit/d4a036886b9f5483a783117db992e0e20cad7415))

- **tui**: Add install progress, health verification, and celebration emoji stream
  ([`209666b`](https://github.com/nWave-ai/nwave-dev/commit/209666b522e407c2c21c712ec5a557c178df7be4))

- **tui**: Extract shared TUI components, eliminate duplication
  ([`0bfb8e7`](https://github.com/nWave-ai/nwave-dev/commit/0bfb8e7c521d5c5db0db7d9f84af72610d8971c6))

- **tui**: Redesign install prompt with version from wheel METADATA
  ([`6d8601d`](https://github.com/nWave-ai/nwave-dev/commit/6d8601d09d663659382ee3c39e909607ca5bb87c))

- **tui**: Strip Tables, Panels, FORGE prefix from forge build CLI
  ([`08b9796`](https://github.com/nWave-ai/nwave-dev/commit/08b9796d786cad6a3db0f3abd533f829060c4fd6))

- **tui**: Strip Tables, Panels, FORGE prefix from forge install CLI
  ([`9096eba`](https://github.com/nWave-ai/nwave-dev/commit/9096eba322305cf7866bade68d220699fd6546ef))


## v1.5.2 (2026-01-22)

### Bug Fixes

- Add PYTHONPATH for build scripts and use correct release packager
  ([`5cde036`](https://github.com/nWave-ai/nwave-dev/commit/5cde036d155293371c62e245dc58860df8af2b95))

- Archive old workflows and fix shellcheck warnings
  ([`4617098`](https://github.com/nWave-ai/nwave-dev/commit/461709842fcaacb3c2cda323769749bea350d8ac))


## v1.5.1 (2026-01-22)

### Bug Fixes

- Replace python with python3 in CI/CD workflow and validation
  ([`2364f77`](https://github.com/nWave-ai/nwave-dev/commit/2364f7702930aef58d4b3b608061e8b405e5da3b))


## v1.4.8 (2026-01-22)

- Initial Release
