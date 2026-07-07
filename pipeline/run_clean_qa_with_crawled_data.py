from clean_qa.run_rule_based_pipeline import PROJECT_ROOT, POLICY_FILE, run_pipeline, write_outputs, print_summary


def main() -> None:
    output_dir = PROJECT_ROOT / "pipeline" / "output" / "rule_based_with_crawled_data"
    result = run_pipeline(
        POLICY_FILE,
        include_gosom_winmart_plus=False,
        include_gosom_topups=True,
        pipeline_run_id="clean_qa_with_crawled_data",
    )
    print_summary(result)
    write_outputs(output_dir, result)
    print("output=", output_dir)


if __name__ == "__main__":
    main()
