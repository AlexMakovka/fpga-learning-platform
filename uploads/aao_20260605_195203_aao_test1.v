module mux2to1(
    input d0,
    input d1,
    input sel,
    output y
);

assign y = sel ? d0 : d1;

endmodule