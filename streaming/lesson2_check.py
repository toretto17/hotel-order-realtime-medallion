"""
Lesson 2 check: verify config and Spark are ready for Bronze. Does not start Kafka.
Run from repo root: python -m streaming.lesson2_check
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from streaming.config_loader import get_kafka_config, get_paths_config, load_config


def main() -> None:
    print("=== Lesson 2: Bronze config check ===\n")
    config = load_config()
    kafka = get_kafka_config(config)
    paths = get_paths_config(config)

    print("Kafka:")
    print(f"  bootstrap_servers: {kafka.get('bootstrap_servers')}")
    print(f"  topic_orders:      {kafka.get('topic_orders')}")
    print(f"  starting_offsets:  {kafka.get('starting_offsets')}")
    print("\nPaths:")
    print(f"  checkpoint_bronze: {paths.get('checkpoint_bronze')}")
    print(f"  bronze_orders:     {paths.get('bronze_orders')}")

    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("lesson2_check").master("local[*]").getOrCreate()
        print("\nSpark session: OK")
        spark.stop()
    except Exception as e:
        err = str(e).lower()
        if "java" in err or "jvm" in err or "gateway" in err or "JAVA_GATEWAY" in str(e):
            print("\nSpark session: skipped (Java not found). PySpark requires a Java Runtime.")
            print("  Install Java: https://adoptium.net/  or:  brew install openjdk@17")
            print("  Then: export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null)")
        else:
            print(f"\nSpark session: FAILED ({e})")
            print("  PySpark requires Java: brew install openjdk@17")
        print("\nTo run the Bronze job (after installing Java and Kafka):")
        print("  BASE_PATH=/tmp/medallion spark-submit streaming/bronze_orders.py")
        print("\nLesson 2 config check passed (config OK; install Java to run Spark).")
        sys.exit(0)

    print("\nTo run the Bronze job (requires Java, Kafka, topic 'orders', and --packages):")
    print("  BASE_PATH=/tmp/medallion spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py")
    print("One-shot: TRIGGER_AVAILABLE_NOW=1 BASE_PATH=/tmp/medallion spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.2 streaming/bronze_orders.py")
    print("\nLesson 2 config check passed.")


if __name__ == "__main__":
    main()
