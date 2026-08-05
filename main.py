"""
Main Integration Runner (Member 1 - Coordinator & Integration Lead)

This script reads all 50 case inputs from input/EC_001.json -> EC_050.json,
executes the Multi-Agent Dispute Resolution pipeline, writes final JSON outputs
to output/EC_xxx.json, logs real trace execution to trace.jsonl, and generates metadata.json.
"""

import os
import json
import time
from dotenv import load_dotenv

from src.contracts import CaseInput, CustomerRequest
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.order_seller_agent import OrderSellerAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.verifier_agent import VerifierAgent

load_dotenv()

MODEL_NAME = "nvidia/nemotron-nano-9b-v2:free"
PARAM_SIZE = "<= 10B parameters"
FRAMEWORK = "Custom Multi-Agent Framework (Python + Pydantic)"


def main():
    start_time = time.time()
    input_dir = "input"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("logging", exist_ok=True)

    print("==================================================================")
    print("  STARTING MULTI-AGENT E-COMMERCE DISPUTE RESOLUTION PIPELINE    ")
    print("==================================================================")

    # Instantiate real teammate agents
    order_seller_agent = OrderSellerAgent()
    payment_agent = PaymentAgent()
    policy_agent = DeliveryAgent()
    verifier_agent = VerifierAgent()

    coordinator = CoordinatorAgent(
        order_seller_agent=order_seller_agent,
        payment_agent=payment_agent,
        policy_agent=policy_agent,
        verifier_agent=verifier_agent
    )

    input_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".json") and f.startswith("EC_")])
    print(f"Found {len(input_files)} cases in '{input_dir}'")

    all_traces = []
    processed_count = 0

    for filename in input_files:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        case_input = CaseInput(
            case_id=data["case_id"],
            opened_at=data["opened_at"],
            customer_request=CustomerRequest(**data["customer_request"]),
            policy_version=data["policy_version"]
        )

        try:
            final_output, case_traces = coordinator.process_case(case_input)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final_output.model_dump(), f, indent=2, ensure_ascii=False)
            
            all_traces.extend(case_traces)
            processed_count += 1
            print(f"[{processed_count}/{len(input_files)}] Processed {filename} -> {final_output.assessment.primary_issue}")
        except Exception as e:
            print(f"ERROR processing {filename}: {e}")

    # Write trace.jsonl
    with open("trace.jsonl", "w", encoding="utf-8") as f:
        for trace in all_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    
    with open(os.path.join("logging", "trace.jsonl"), "w", encoding="utf-8") as f:
        for trace in all_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    elapsed_time = round(time.time() - start_time, 2)

    # Write metadata.json
    metadata = {
        "model": MODEL_NAME,
        "parameter_size": PARAM_SIZE,
        "framework": FRAMEWORK,
        "runtime_seconds": elapsed_time,
        "processed_cases": processed_count
    }

    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(os.path.join("logging", "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n==================================================================")
    print(f" Completed processing {processed_count}/{len(input_files)} cases in {elapsed_time}s!")
    print(f" Outputs written to: {output_dir}/")
    print(f" Traces written to: trace.jsonl")
    print(f" Metadata written to: metadata.json")
    print("==================================================================")


if __name__ == "__main__":
    main()
