from value_semantics.core.table import TableProfile, ColumnProfile, ColumnStats


class DataFrameProfiler:
    def profile(self, df, table_name: str, sample_size: int = 1000) -> TableProfile:
        sample_df = df.head(sample_size)

        columns = []
        for col in df.columns:
            series = df[col]
            non_null = series.dropna()

            stats = ColumnStats(
                sample_values=non_null.head(20).tolist(),
                min=non_null.min() if not non_null.empty else None,
                max=non_null.max() if not non_null.empty else None,
                distinct_count=int(non_null.nunique()),
                null_count=int(series.isna().sum()),
                row_count=int(len(series)),
            )

            columns.append(
                ColumnProfile(
                    name=str(col),
                    declared_type=str(series.dtype),
                    stats=stats,
                )
            )

        return TableProfile(
            table_name=table_name,
            columns=columns,
            row_samples=sample_df.to_dict(orient="records"),
        )
