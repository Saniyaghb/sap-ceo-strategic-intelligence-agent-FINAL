from collectors.live_collect import collect_all
from processing.clean import prepare_master_data
from processing.chunk import create_chunks
from rag.vector_store import build_vector_store


def main():
    collect_all()
    prepare_master_data()
    create_chunks()
    build_vector_store(reset=True)
    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
