/* =========  STATUTORY RULES (only what's needed for this case)  ========= */

% free allowances -----------------------------------------------------------
carry_on_allowed(bag(ID,L,W,H,_)) :-
        L =< 22, W =< 14, H =< 9,                 % carry-on size limit
        ID = 1.                                   % Robert uses the 1st bag as carry-on

% base checked-bag fee (Basic Economy, wholly within the U.S.) -------------
base_checked_fee(Order,40) :- Order =:= 1.        % 1st checked
base_checked_fee(Order,45) :- Order =:= 2.        % 2nd checked
base_checked_fee(Order,150) :- Order =:= 3.       % 3rd checked
base_checked_fee(Order,200) :- Order >= 4.        % 4th and beyond

% oversize fee (domestic) ----------------------------------------------------
oversize_fee(SumDim,Fee) :-
        SumDim =< 62, !, Fee = 0.
oversize_fee(SumDim,30) :-
        SumDim =< 65, !.
oversize_fee(SumDim,200) :-
        SumDim =< 115, !.

% overweight fee (domestic) --------------------------------------------------
overweight_fee(W,Fee) :-
        W =< 50, !,   Fee = 0.
overweight_fee(W,30) :-
        W =< 53, !.
overweight_fee(W,100) :-
        W =< 70, !.
overweight_fee(W,200) :-
        W =< 100, !.

% choose the higher of oversize / overweight -------------------------------
extra_fee(Oversize,Overweight,Chosen) :-
        (Oversize >= Overweight -> Chosen = Oversize ; Chosen = Overweight).

/* =========  FACTS - Robert's flight and bags  ========= */

ticket_price(141).              % flight ticket itself

% bag(ID,Length,Width,Height,Weight).
bag( 1,20,12, 7,  8).            % carried on
bag( 2,48,28,19, 51).
bag( 3,49,32,23, 52).
bag( 4,35,19,11, 81).
bag( 5,46,28,18, 52).
bag( 6,36,15,12, 66).
bag( 7,40,20,17, 56).
bag( 8,45,31,23, 51).
bag( 9,33,18,12, 86).
bag(10,52,29,28, 89).
bag(11,53,31,30, 73).

/* =========  DERIVED PREDICATES  ========= */

% list of checked bags in the order they appear AFTER removing the free carry-on
checked_bag_list(Checked) :-
        findall(bag(ID,L,W,H,WT),
                (bag(ID,L,W,H,WT), \+ carry_on_allowed(bag(ID,L,W,H,WT))),
                Checked).

% fee for an individual checked bag ----------------------------------------
checked_bag_fee(Order,bag(_,L,W,H,WT),Fee) :-
        base_checked_fee(Order,BaseFee),
        SD is L+W+H,
        oversize_fee(SD,OSFee),
        overweight_fee(WT,OWFee),
        extra_fee(OSFee,OWFee,Extra),
        Fee is BaseFee + Extra.

% sum of all checked-bag fees ----------------------------------------------
bag_fees_sum(Sum) :-
        checked_bag_list(Checked),
        bag_fees_sum(Checked,1,0,Sum).

bag_fees_sum([],_,Acc,Acc).
bag_fees_sum([Bag|Rest],Order,Acc,Sum) :-
        checked_bag_fee(Order,Bag,F),
        Acc1 is Acc + F,
        Order1 is Order + 1,
        bag_fees_sum(Rest,Order1,Acc1,Sum).

/* =========  TOTAL COST  ========= */

total_cost(Total) :-
        ticket_price(Ticket),
        bag_fees_sum(BagFees),
        Total is Ticket + BagFees.

/* =========  QUERY  ========= */

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.