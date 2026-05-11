import SwiftUI

struct DailyState: Codable {
    let latestRecoveryDate: String
    let validationStatus: String
    let sleepHours: String
    let hrv: HRV
    let stress: String
    let restingHR: String
    let recoveryState: RecoveryState?
    let decision: Decision
    let recommendation: String
    let rationale: String

    enum CodingKeys: String, CodingKey {
        case latestRecoveryDate = "latest_recovery_date"
        case validationStatus = "validation_status"
        case sleepHours = "sleep_hours"
        case hrv
        case stress
        case restingHR = "resting_hr"
        case recoveryState = "recovery_state"
        case decision
        case recommendation
        case rationale
    }
}

struct HRV: Codable {
    let status: String?
    let hrvValue: String
    let hrv5MinHigh: String?
    let hrvUnit: String?
    let hrvBalance: String?
    let hrvRisk: String?
    let hrvMessage: String?

    enum CodingKeys: String, CodingKey {
        case status
        case hrvValue = "hrv_value"
        case hrv5MinHigh = "hrv_5min_high"
        case hrvUnit = "hrv_unit"
        case hrvBalance = "hrv_balance"
        case hrvRisk = "hrv_risk"
        case hrvMessage = "hrv_message"
    }
}

struct Decision: Codable {
    let decision: String
    let intensity: String
    let suggestedActivity: String
    let reason: String?

    enum CodingKeys: String, CodingKey {
        case decision
        case intensity
        case suggestedActivity = "suggested_activity"
        case reason
    }
}

struct RecoveryState: Codable {
    let recoveryScore: Int?
    let recoveryLevel: String?

    enum CodingKeys: String, CodingKey {
        case recoveryScore = "recovery_score"
        case recoveryLevel = "recovery_level"
    }
}

struct ContentView: View {
    private let state = DailyState.mock

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    metricsGrid
                    recommendationCard
                    rationaleCard
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Stramin")
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Daily Recovery")
                .font(.title2)
                .fontWeight(.semibold)

            HStack {
                Label(state.latestRecoveryDate, systemImage: "calendar")
                Spacer()
                Text(state.validationStatus.capitalized)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.green.opacity(0.15))
                    .foregroundStyle(.green)
                    .clipShape(Capsule())
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
    }

    private var metricsGrid: some View {
        LazyVGrid(
            columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12)
            ],
            spacing: 12
        ) {
            MetricTile(title: "Sleep", value: "\(state.sleepHours)h", systemImage: "bed.double.fill")
            MetricTile(title: "HRV", value: "\(state.hrv.hrvValue) \(state.hrv.hrvUnit ?? "ms")", systemImage: "waveform.path.ecg")
            MetricTile(title: "Stress", value: state.stress, systemImage: "gauge.with.dots.needle.50percent")
            MetricTile(title: "Resting HR", value: "\(state.restingHR) bpm", systemImage: "heart.fill")
        }
    }

    private var recommendationCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recommendation")
                .font(.headline)

            Text(state.recommendation)
                .font(.title3)
                .fontWeight(.semibold)

            Divider()

            InfoRow(label: "Decision", value: state.decision.decision.displayLabel)
            InfoRow(label: "Intensity", value: state.decision.intensity.displayLabel)
            InfoRow(label: "Suggested activity", value: state.decision.suggestedActivity.displayLabel)
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var rationaleCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Rationale")
                .font(.headline)

            Text(state.rationale)
                .font(.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct MetricTile: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(systemName: systemImage)
                .foregroundStyle(.blue)

            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)

            Text(value)
                .font(.title3)
                .fontWeight(.semibold)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct InfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
                .multilineTextAlignment(.trailing)
        }
        .font(.subheadline)
    }
}

private extension DailyState {
    static let mock: DailyState = {
        let json = """
        {
          "latest_recovery_date": "2026-05-10",
          "validation_status": "ready",
          "sleep_hours": "7.43",
          "hrv": {
            "status": "balanced",
            "hrv_value": "34",
            "hrv_5min_high": "48",
            "hrv_unit": "ms",
            "hrv_balance": "within_baseline",
            "hrv_risk": "stable",
            "hrv_message": "HRV is within your normal baseline range."
          },
          "stress": "34",
          "resting_hr": "59",
          "recovery_state": {
            "recovery_score": 86,
            "recovery_level": "good"
          },
          "decision": {
            "decision": "train",
            "intensity": "normal",
            "suggested_activity": "weight_training",
            "reason": "Recovery level is good and fatigue trend is not worsening."
          },
          "recommendation": "train / normal / weight_training",
          "rationale": "恢復等級為 good，且疲勞趨勢沒有惡化，可以正常訓練。"
        }
        """

        do {
            let data = Data(json.utf8)
            return try JSONDecoder().decode(DailyState.self, from: data)
        } catch {
            return DailyState(
                latestRecoveryDate: "Unavailable",
                validationStatus: "error",
                sleepHours: "-",
                hrv: HRV(
                    status: nil,
                    hrvValue: "-",
                    hrv5MinHigh: nil,
                    hrvUnit: "ms",
                    hrvBalance: nil,
                    hrvRisk: nil,
                    hrvMessage: nil
                ),
                stress: "-",
                restingHR: "-",
                recoveryState: nil,
                decision: Decision(
                    decision: "unknown",
                    intensity: "unknown",
                    suggestedActivity: "unknown",
                    reason: nil
                ),
                recommendation: "Unavailable",
                rationale: "Mock daily_state.json could not be decoded."
            )
        }
    }()
}

private extension String {
    var displayLabel: String {
        split(separator: "_")
            .map { word in
                word.prefix(1).uppercased() + word.dropFirst()
            }
            .joined(separator: " ")
    }
}

#Preview {
    ContentView()
}
