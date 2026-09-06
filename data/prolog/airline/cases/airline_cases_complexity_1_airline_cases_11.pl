/* ----------  Statutory rules needed for this case  ---------- */

/*  Oversize fees for itineraries to / from South Korea (same as the
    "China-/Japan-/Korea-/India-/Hong-Kong / Australia / New-Zealand"
    column in the statute)                                            */

oversize_fee(Size, Fee) :-
    Size  =< 62,                     % standard size
    Fee = 0.

oversize_fee(Size, Fee) :-
    Size  > 62,
    Size =< 65,                      % 62-65 in
    Fee = 30.

oversize_fee(Size, Fee) :-
    Size  > 65,                      % 65-115 in
    Fee = 200.

/*  Over-weight fees for itineraries to / from South Korea            */

overweight_fee(Weight, Fee) :-
    Weight =< 50,                    % standard weight
    Fee = 0.

overweight_fee(Weight, Fee) :-
    Weight  > 50,
    Weight =< 53,                    % 50-53 lb
    Fee = 30.

overweight_fee(Weight, Fee) :-
    Weight  > 53,
    Weight =< 70,                    % 53-70 lb
    Fee = 100.

overweight_fee(Weight, Fee) :-       % 70-100 lb
    Weight  > 70,
    Weight =< 100,
    Fee = 450.

/*  Extra charge for a bag that is either oversize, overweight, or both.
    Statute: "The higher fee between oversize and overweight applies."   */

bag_extra_fee(Weight, Size, Fee) :-
    oversize_fee(Size, O),
    overweight_fee(Weight, W),
    (O >= W -> Fee = O ; Fee = W).

/*  Base checked-bag fee for Main Plus on this route

    - First 2 checked bags are free (Main Cabin 1st is free on this
      route, Main Plus adds 1 extra free bag).
    - Bags 3 + cost $200 each (statute tables, "To / from ... South Korea")
*/

base_bag_fee(BagNo, Fee) :- BagNo =< 2, Fee = 0.         % bag 1 & 2
base_bag_fee(BagNo, Fee) :- BagNo >= 3, Fee = 200.       % bag 3+

/*  Total fee for one bag = base fee + extra (oversize / overweight) */

bag_total_fee(BagNo, Weight, Size, TotalFee) :-
    base_bag_fee(BagNo, Base),
    bag_extra_fee(Weight, Size, Extra),
    TotalFee is Base + Extra.


/* ----------  Facts for Emily's trip  ---------- */

flight_ticket(572).                 % price of the ticket in USD

/*  Checked bags (carry-on is free and therefore omitted)              */
/*  Format: bag(Index, Weight, Length, Width, Height).                 */

bag(1, 65, 34, 21,  9).             % item 2 in the description
bag(2, 67, 33, 21, 11).             % item 3
bag(3, 65, 34, 21, 13).             % item 4
bag(4, 53, 38, 17,  9).             % item 5
bag(5, 53, 35, 17, 12).             % item 6
bag(6, 78, 37, 14, 12).             % item 7
bag(7, 62, 45, 25, 23).             % item 8


/* ----------  Aggregate computation  ---------- */

bags_total_fee(Total) :-
    findall(Fee,
        ( bag(N,W,L,Wi,H),
          Size is L + Wi + H,
          bag_total_fee(N,W,Size,Fee)
        ),
        Fees),
    sum_list(Fees, Total).

total_cost(Total) :-
    bags_total_fee(BagFees),
    flight_ticket(Ticket),
    Total is Ticket + BagFees.


/* ----------  Query & printing  ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.